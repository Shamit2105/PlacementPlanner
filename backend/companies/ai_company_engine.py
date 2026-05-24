import os
import json
import logging
import re
import ast  # <--- Needed for the Silver Bullet fix
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger('companies')

def enrich_company_questions(company_name, raw_questions_list):
    """
    Feeds raw scraped questions to the AI and returns structured JSON.
    """
    if not raw_questions_list:
        return None

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY is missing from .env!")
        return None

    # Note: Make sure your model name here is correct for the API you are using.
    llm = ChatGoogleGenerativeAI(
        model="gemma-4-26b-a4b-it", # Reverted to standard flash for stability, change back if needed
        google_api_key=api_key,
        temperature=0.2 
    )

    template = """
    You are an expert Senior Software Engineer and Technical Interview Coach. 
    Analyze the following scraped interview questions asked by {company}.
    
    Raw Questions:
    {questions}
    
    Extract the core data structures, algorithms, or concepts being tested. 
    Respond ONLY with a valid JSON object matching this exact structure, with NO markdown formatting, NO backticks, and NO extra text:
    {{
        "top_topics": ["List of 3 to 5 core DSA topics like Array, Dynamic Programming, etc."],
        "difficulty": "Easy, Medium, or Hard",
        "recommended_leetcode_concepts": ["List of 3 specific LeetCode concepts/tags to practice"],
        "summary": "A 2-sentence summary of what this company focuses on."
    }}
    """
    
    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm
    
    # Combine list into one string to save tokens
    questions_text = "\n".join([f"- {q}" for q in raw_questions_list])
    
    try:
        response = chain.invoke({
            "company": company_name,
            "questions": questions_text
        })
        
        raw_content = response.content
        text_content = ""
        
        # 1. Safely handle the List of Dicts format (The Silver Bullet Extraction)
        if isinstance(raw_content, list):
            for block in raw_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_content += block.get("text", "")
        elif isinstance(raw_content, str):
            try:
                # If Langchain stringified the list, safely evaluate it
                parsed_list = ast.literal_eval(raw_content.strip())
                if isinstance(parsed_list, list):
                    for block in parsed_list:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_content += block.get("text", "")
            except (ValueError, SyntaxError):
                pass
                
            # If it was just a normal string all along
            if not text_content:
                text_content = raw_content

        # 2. THE SILVER BULLET REGEX
        # Explicitly hunt down the JSON starting with "top_topics"
        match = re.search(r'\{\s*"top_topics".*?\}', text_content, re.DOTALL)
        
        if match:
            clean_json_string = match.group(0)
            return json.loads(clean_json_string) # <--- YOU WERE MISSING THIS RETURN!
        else:
            logger.error(f"Regex failed to find JSON for {company_name}. Extracted text: {text_content}")
            return None
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON Error for {company_name}: {e}.")
        return None
    except Exception as e:
        logger.error(f"AI Engine Error for {company_name}: {e}")
        return None