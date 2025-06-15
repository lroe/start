// File: frontend/src/App.js

import React from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  NavLink, // <-- Use NavLink for active styles
  Navigate,
  useLocation
} from 'react-router-dom';

// Import the AuthProvider and the useAuth hook
import { AuthProvider, useAuth } from './contexts/AuthContext';

// Import all your page components
import DeckAnalyzerPage from './pages/DeckAnalyzerPage';
import PitchPracticePage from './pages/PitchPracticePage';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';

// Import the main stylesheet
import './App.css';

// --- MainNav Component Definition ---
// This component displays the main navigation bar.
function MainNav() {
    const { currentUser, logout } = useAuth();

    const handleLogout = async () => {
        try {
            await logout();
        } catch (error) {
            console.error("Failed to log out:", error);
        }
    };

    return (
        <nav className="main-nav">
            <div className="nav-links">
                <NavLink to="/" end>Home</NavLink>
                {currentUser && <NavLink to="/analyze">Deck Analyzer</NavLink>}
                {currentUser && <NavLink to="/practice">Live Pitch Practice</NavLink>}
            </div>
            <div className="nav-auth">
                {currentUser ? (
                    <>
                        <span>{currentUser.email}</span>
                        <button onClick={handleLogout} className="logout-btn">Logout</button>
                    </>
                ) : (
                    <NavLink to="/login" className="login-btn">Login / Sign Up</NavLink>
                )}
            </div>
        </nav>
    );
}

// --- ProtectedRoute Component Definition ---
// This wrapper component protects routes that require authentication.
function ProtectedRoute({ children }) {
    const { currentUser } = useAuth();
    const location = useLocation();

    if (!currentUser) {
        // If the user is not logged in, redirect to the /login page
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    // If the user is logged in, render the child component (the protected page)
    return children;
}


// --- Main App Component ---
// This is the root of your application.
function App() {
  return (
    <AuthProvider>
      <Router>
        <MainNav />
        <main className="container">
          <Routes>
            {/* Public Routes */}
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />

            {/* Protected Routes */}
            <Route
              path="/analyze"
              element={<ProtectedRoute><DeckAnalyzerPage /></ProtectedRoute>}
            />
            <Route
              path="/practice"
              element={<ProtectedRoute><PitchPracticePage /></ProtectedRoute>}
            />
            
            {/* Catch-all route for unknown paths */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </Router>
    </AuthProvider>
  );
}

export default App;