
// File: frontend/src/contexts/AuthContext.js

import React, { useContext, useState, useEffect, createContext } from 'react';
import { initializeApp } from 'firebase/app';
import { 
    getAuth, 
    onAuthStateChanged,
    createUserWithEmailAndPassword,
    signInWithEmailAndPassword,
    signOut,
    signInWithCustomToken
} from 'firebase/auth';
// You don't need firestore here unless you're fetching user profiles directly in the context
// import { getFirestore } from 'firebase/firestore'; 

// --- Your Firebase Configuration ---
// It's better to put these in a .env file for security, but this works.
const firebaseConfig = {
  apiKey: "AIzaSyB-HLZWxE7y4FwunHvEw-BH_IkOr1H0SpI",
  authDomain: "pitchine-ed6c2.firebaseapp.com",
  projectId: "pitchine-ed6c2",
  storageBucket: "pitchine-ed6c2.appspot.com",
  messagingSenderId: "323898270266",
  appId: "1:323898270266:web:d4edd9b54082db17c68b03",
  measurementId: "G-9R50037REV"
};
// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
// const db = getFirestore(app); // Optional, if needed

// Create the context
const AuthContext = createContext();

// Create a custom hook to easily use the context
export function useAuth() {
    return useContext(AuthContext);
}

// Create the Provider component
export function AuthProvider({ children }) {
    const [currentUser, setCurrentUser] = useState(null);
    const [loading, setLoading] = useState(true); // To check if auth state has been determined

    // --- Authentication Functions ---

    function signup(email, password) {
        return createUserWithEmailAndPassword(auth, email, password);
    }

    function login(email, password) {
        return signInWithEmailAndPassword(auth, email, password);
    }

    function logout() {
        return signOut(auth);
    }

    function signInWithGoogle() {
        // This redirects the user, so the backend handles the callback
        window.location.href = 'https://pitch-vzva.onrender.com/login/google'; // Use your actual backend URL
    }

    function handleGoogleCallback() {
        // This function should be called ONCE when the app loads
        // to check for the token from the backend redirect.
        const urlParams = new URLSearchParams(window.location.search);
        const loginToken = urlParams.get('logintoken');
        const error = urlParams.get('error');

        if (error) {
            alert("Google Sign-In failed on the server. Please try again.");
            // Clean the URL
            window.history.replaceState({}, document.title, window.location.pathname);
        }

        if (loginToken) {
            setLoading(true);
            signInWithCustomToken(auth, loginToken)
                .then(() => {
                    console.log("Signed in with custom token successfully!");
                    window.history.replaceState({}, document.title, window.location.pathname);
                })
                .catch((err) => {
                    console.error("Error signing in with custom token:", err);
                    alert("Could not complete sign-in. Error: " + err.message);
                    window.history.replaceState({}, document.title, window.location.pathname);
                })
                .finally(() => {
                    // The onAuthStateChanged listener will handle setting the user
                });
        }
    }

    // --- Auth State Listener ---
    useEffect(() => {
        // Check for Google callback token on initial load
        handleGoogleCallback();

        // This is the core listener that sets the user.
        // It returns an `unsubscribe` function that React will call on cleanup.
        const unsubscribe = onAuthStateChanged(auth, user => {
            setCurrentUser(user);
            setLoading(false); // Auth state is now known
        });

        return unsubscribe; // Cleanup on unmount
    }, []); // Empty dependency array means this runs only once on mount

    // The value provided to all consuming components
    const value = {
        currentUser,
        signup,
        login,
        logout,
        signInWithGoogle
    };

    // Render children only after auth state is determined
    return (
        <AuthContext.Provider value={value}>
            {!loading && children}
        </AuthContext.Provider>
    );
}
