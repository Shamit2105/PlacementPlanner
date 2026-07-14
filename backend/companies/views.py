import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status, filters
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from celery.result import AsyncResult


from .llm_service import LLMService
from .vector_service import VectorService
from .filters import QuestionFilter
from .models import Company, Question, Topic, ProcessingStatus
from .serializers import (
    CompanySerializer,
    QuestionCreateSerializer,
    QuestionDetailSerializer,
    QuestionListSerializer,
    SemanticSearchSerializer,
    ScrapeRequestSerializer,
    TopicSerializer,
)
from .tasks import scrape_and_ingest_questions

logger = logging.getLogger(__name__)


class CompanyListCreateView(generics.ListCreateAPIView):
   
    queryset         = Company.objects.all()
    serializer_class = CompanySerializer
    filter_backends  = [filters.SearchFilter, filters.OrderingFilter]
    search_fields    = ["name", "slug"]
    ordering_fields  = ["name", "created_at"]


class TopicListCreateView(generics.ListCreateAPIView):
   
    serializer_class = TopicSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["question_type"]
    search_fields    = ["name"]

    def get_queryset(self):
        return Topic.objects.all().order_by("question_type", "name")



class QuestionListCreateView(generics.ListCreateAPIView):
   
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class  = QuestionFilter
    search_fields    = ["interview_question",]
    ordering_fields  = ["times_used", "created_at", "difficulty"]
    ordering         = ["-created_at"]

    def get_queryset(self):
        return (
            Question.objects.filter(is_duplicate=False)
                            .prefetch_related("companies", "topics")
                            .defer("embedding",  "interview_answer")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return QuestionCreateSerializer
        return QuestionListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.save()
        return Response(
            QuestionDetailSerializer(question).data,
            status=status.HTTP_201_CREATED,
        )


# ─── Question Detail / Delete ─────────────────────────────────────────────────

class QuestionDetailView(generics.RetrieveDestroyAPIView):
    """
    GET    /questions/<id>/ → full detail including reference answer
    DELETE /questions/<id>/ → remove from bank
    """
    queryset         = Question.objects.prefetch_related("companies", "topics")
    serializer_class = QuestionDetailSerializer

class GenerateAnswerView(APIView):
    """
    POST /questions/<id>/generate-answer/
    Generates an interview_answer for a question if it doesn't exist.
    """
    def post(self, request, pk):
        try:
            question = Question.objects.get(pk=pk)
        except Question.DoesNotExist:
            return Response({"error": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

        if question.interview_answer:
            return Response({"message": "Answer already exists.", "answer": question.interview_answer})

        try:
            llm = LLMService()
            ans = llm.generate_answer(question.interview_question, question.question_type)
            question.interview_answer = ans
            question.save(update_fields=["interview_answer"])
            return Response({"message": "Answer generated.", "answer": ans})
        except Exception as e:
            logger.error(f"Failed to generate answer for Question {pk}: {e}")
            return Response({"error": "Failed to generate answer."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SemanticSearchView(APIView):
    def post(self, request):
        serializer = SemanticSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data



        try:
            llm = LLMService()
            query_embedding = llm.get_query_embedding(data["query"])
        except Exception as exc:
            logger.error("Embedding computation failed: %s", exc)
            return Response(
                {"error": "Failed to compute query embedding. Try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if query_embedding is None:
            return Response(
                {"error": "Embedding returned None. Gemini may be rate-limiting."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        vs      = VectorService()
        results = vs.semantic_search(
            query_embedding=query_embedding,
            question_type=data.get("question_type") or None,
            company_slug=data.get("company_slug") or None,
            limit=data.get("limit", 10),
        )

        # Annotate results with the cosine distance for frontend display
        questions_data = []
        for q in results:
            q_data = QuestionListSerializer(q).data
            q_data["similarity_score"] = round(1 - getattr(q, "distance", 1.0), 4)
            questions_data.append(q_data)

        return Response({"count": len(questions_data), "results": questions_data})


class SimilarQuestionsView(APIView):


    def get(self, request, pk):
        try:
            limit = int(request.query_params.get("limit", 3))
        except (TypeError, ValueError):
            limit = 3
        limit = max(0, min(limit, 3))
        vs      = VectorService()
        results = vs.get_similar_questions(question_id=pk, limit=limit)
        
        data = []
        for q in results:
            q_data = QuestionListSerializer(q).data
            q_data["similarity_score"] = round(1 - getattr(q, "distance", 1.0), 4)
            data.append(q_data)
            
        return Response({"count": len(data), "results": data})


class TriggerScrapeView(APIView):
    

    def get(self, request):
        return Response(
            {
                "endpoint": "/api/v1/questions/scrape/",
                "method": "POST",
                "example": {
                    "question_type": "DSA_CODING",
                    "company_name": "Amazon",
                    "target_count": 5,
                },
            }
        )

    def post(self, request):
        serializer = ScrapeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        question_type = data.get("question_type", "")

        # target_count is validated by the serializer (max=5) and also
        # enforced by MAX_PAGES_TOTAL inside the scraper.
        task = scrape_and_ingest_questions.delay(
            question_type=question_type,
            company_name=data.get("company_name", ""),
            target_count=data.get("target_count", 5),
        )

        return Response(
            {
                "message": "Scraping task queued.",
                "task_id": task.id,
                "question_type": question_type,
                "scope": "all question types found on each page",
                "poll_url": f"/api/v1/tasks/{task.id}/status/",
            },
            status=status.HTTP_202_ACCEPTED,
        )


@api_view(["GET"])
def task_status_view(request, task_id):
    
    result = AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "status": result.status,
    }
    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            response["error"] = str(result.result)

    return Response(response)



@api_view(["GET"])
def question_bank_stats(request):
   
    from django.db.models import Count
    from .models import QuestionType

    by_type = dict(
        Question.objects.filter(is_duplicate=False)
                        .values_list("question_type")
                        .annotate(count=Count("id"))
                        .values_list("question_type", "count")
    )
    by_status = dict(
        Question.objects.values_list("status")
                        .annotate(count=Count("id"))
                        .values_list("status", "count")
    )
    by_source = dict(
        Question.objects.filter(is_duplicate=False)
                        .values_list("source")
                        .annotate(count=Count("id"))
                        .values_list("source", "count")
    )
    embedded_pct = (
        Question.objects.filter(status=ProcessingStatus.EMBEDDED).count()
        / max(Question.objects.count(), 1)
        * 100
    )

    return Response({
        "total": Question.objects.count(),
        "unique": Question.objects.filter(is_duplicate=False).count(),
        "embedded_percent": round(embedded_pct, 1),
        "by_type": by_type,
        "by_status": by_status,
        "by_source": by_source,
    })
