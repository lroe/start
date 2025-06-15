// File: frontend/src/pages/HomePage.js

import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// --- A "Paul Graham-style" Landing Page ---
function HomePage() {
    const { currentUser } = useAuth();
    const navigate = useNavigate();

    // The primary CTA button for a new visitor.
    // It guides them to the first logical step: analyzing their deck.
    // The ProtectedRoute component will handle redirecting them to login first.
    const handleGetStarted = () => {
        navigate('/analyze');
    };

    return (
        <div className="home-page-pg">
            {/* === HERO SECTION: WHAT IS THIS? === */}
            <header className="hero-pg">
                <h1>Don't Practice on VCs.</h1>
                <p>
                    Our AI simulator is the private, high-pressure environment to fail, learn, and perfect your pitch before it counts.
                </p>
                {!currentUser && (
                    <button onClick={handleGetStarted} className="btn hero-btn-pg">
                        Analyze Your Deck First
                    </button>
                )}
            </header>

            {/* === FEATURES SECTION: HOW DOES IT WORK? === */}
            <div className="features-pg">
                <div className="feature-card-pg content-card">
                    <div className="feature-header">
                        <span className="feature-number">1</span>
                        <h3>Find Flaws in Your Story.</h3>
                    </div>
                    <p>
                        Upload your pitch deck. Our AI reads it like a partner at a top firm,
                        identifying weak arguments, unclear statements, and missed opportunities.
                        Get a brutally honest report in seconds, before you send it to a real VC.
                    </p>
                    <Link to="/analyze" className="feature-link">Try the Deck Analyzer →</Link>
                </div>

                <div className="feature-card-pg content-card">
                    <div className="feature-header">
                        <span className="feature-number">2</span>
                        <h3>Master Your Delivery.</h3>
                    </div>
                    <p>
                        Enter a simulation with AI investors programmed with distinct personalities—the
                        skeptic, the visionary, the operator. They don't follow a script. They react
                        to your answers, interrupt you, and test your conviction under pressure.
                    </p>
                     <Link to="/practice" className="feature-link">Enter the Simulator →</Link>
                </div>
            </div>

            {/* === PHILOSOPHY SECTION: WHY DOES THIS MATTER? === */}
            <footer className="final-quote-pg">
                <p>"A 'no' on your idea is fine. A 'no' because they didn't understand your idea is fatal."</p>
            </footer>
        </div>
    );
}

export default HomePage;