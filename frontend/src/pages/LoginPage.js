// File: frontend/src/pages/LoginPage.js

import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

// All styling is now handled by the global App.css file.

// --- The LoginPage Component ---
function LoginPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { signup, login, signInWithGoogle } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();
    const from = location.state?.from?.pathname || "/";

    const handleEmailPasswordSignup = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await signup(email, password);
            navigate(from, { replace: true });
        } catch (err) {
            setError('Failed to create an account. Please try again.');
        }
        setLoading(false);
    };

    const handleEmailPasswordLogin = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await login(email, password);
            navigate(from, { replace: true });
        } catch (err) {
            setError('Failed to log in. Check your email and password.');
        }
        setLoading(false);
    };

    const handleGoogleSignIn = () => {
        setError('');
        try {
            signInWithGoogle();
        } catch (err) {
            setError('Failed to start Google Sign-In.');
        }
    };

    return (
        <div className="content-card" style={{ maxWidth: '420px', margin: '40px auto' }}>
            <h2>Get Started</h2>
            
            {error && <p className="error-message">{error}</p>}
            
            <form style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                <div className="form-group">
                     <input
                        id="email"
                        type="email"
                        placeholder="Email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                    />
                </div>
                <div className="form-group">
                    <input
                        id="password"
                        type="password"
                        placeholder="Password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                    />
                </div>
                <div style={{ display: 'flex', gap: '10px' }}>
                    <button onClick={handleEmailPasswordLogin} disabled={loading} className="btn" style={{ flex: 1 }}>
                        {loading ? 'Logging in...' : 'Login'}
                    </button>
                    <button onClick={handleEmailPasswordSignup} disabled={loading} className="btn btn-secondary" style={{ flex: 1 }}>
                        {loading ? '...' : 'Sign Up'}
                    </button>
                </div>
            </form>

            <div style={{ margin: '20px 0', color: 'var(--secondary-text)', fontSize: '0.9rem', textAlign: 'center' }}>or</div>

            <button onClick={handleGoogleSignIn} disabled={loading} className="btn btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
                <img src="https://img.icons8.com/color/16/000000/google-logo.png" alt="Google logo"/>
                Sign in with Google
            </button>
        </div>
    );
}

export default LoginPage;