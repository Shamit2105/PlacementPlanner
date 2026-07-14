import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import ProtectedRoute from './components/auth/ProtectedRoute';
import Navbar from './components/layout/Navbar';
import { AuthProvider } from './context/AuthContext';
import Companies from './pages/Companies';
import CompanyDetail from './pages/CompanyDetail';
import Experiences from './pages/Experiences';
import Home from './pages/Home';
import Interviews from './pages/Interviews';
import Login from './pages/Login';
import OpsLab from './pages/OpsLab';
import Profile from './pages/Profile';
import Register from './pages/Register';

const App: React.FC = () => {
  return (
    <AuthProvider>
      <Router>
        <div className="min-h-screen">
          <Navbar />
          <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/companies" element={<Companies />} />
              <Route path="/companies/:id" element={<CompanyDetail />} />
              <Route path="/experiences" element={<Experiences />} />
              <Route path="/ops" element={<OpsLab />} />
              <Route
                path="/interviews"
                element={
                  <ProtectedRoute>
                    <Interviews />
                  </ProtectedRoute>
                }
              />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route
                path="/profile"
                element={
                  <ProtectedRoute>
                    <Profile />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </main>
        </div>
      </Router>
    </AuthProvider>
  );
};

export default App;
