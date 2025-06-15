// File: frontend/src/pages/PitchPracticePage.js

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import '../App.css'; // Use the main App.css file

// This URL will be 'http://localhost:8000' locally and your production URL when deployed
const BACKEND_HTTP_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

// This converts the HTTP URL to a WebSocket URL (http -> ws, https -> wss)
const BACKEND_WS_URL = BACKEND_HTTP_URL.replace(/^http/, 'ws') + "/ws";
const PITCH_DURATION_SECONDS = 120;

// ############################################################################
// ## UI SUB-COMPONENTS (Themed)
// ############################################################################

const ReportDisplay = ({ reportData, onPracticeAgain }) => {
    if (!reportData || !reportData.analysis_report) {
        return <p>No report data available.</p>;
    }
    
    const { analysis_report, startup_details } = reportData;
    const { default_alive_dead, pillars, brutal_feedback, top_3_areas } = analysis_report;

    const getVerdictClass = (verdict) => {
        if (!verdict) return 'neutral';
        const lowerVerdict = verdict.toLowerCase();
        if (lowerVerdict.includes('dead')) return 'dead';
        if (lowerVerdict.includes('alive')) return 'alive';
        return 'neutral';
    };

    return (
        <div id="reportArea">
             <div className="content-card">
                <h2 style={{ textAlign: 'center' }}>Pitch Analysis for "{startup_details.name}"</h2>
                <div className={`status-assessment ${getVerdictClass(default_alive_dead)}`}>
                    <strong>Overall Assessment:</strong> {default_alive_dead || 'Analysis not available.'}
                </div>
            </div>

            {pillars && <div className="content-card">
                <h2>Pillar Breakdown</h2>
                {Object.entries(pillars).map(([pillarName, data]) => (
                    <div key={pillarName} style={{ marginBottom: '25px' }}>
                        <h3>
                            {pillarName}
                            {data.score && data.score !== "N/A" && <span className="score">{data.score}/5</span>}
                        </h3>
                        {data.feedback && <ul className="report-list">
                            {data.feedback.map((fb, i) => (
                                <li key={i}>{fb.replace(/^\*+/, '').trim()}</li>
                            ))}
                        </ul>}
                    </div>
                ))}
            </div>}

            {brutal_feedback && <div className="content-card">
                <h2>Brutally Honest Feedback</h2>
                <ul className="report-list">
                    {brutal_feedback.map((fb, i) => (
                        <li key={i}>{fb.replace(/^\*+/, '').trim()}</li>
                    ))}
                </ul>
            </div>}
            
            {top_3_areas && <div className="content-card">
                <h2>Top 3 Areas for Next Practice</h2>
                 <ul className="report-list">
                    {top_3_areas.map((fb, i) => (
                        <li key={i}>{fb.replace(/^\*+/, '').trim()}</li>
                    ))}
                </ul>
            </div>}

            <div style={{ textAlign: 'center', marginTop: '30px' }}>
                <button onClick={onPracticeAgain} className="btn">Practice Again</button>
            </div>
        </div>
    );
};


const TimerBar = ({ remainingSeconds, totalSeconds }) => {
    const percentage = (remainingSeconds / totalSeconds) * 100;
    let barClass = 'timer-bar';
    if (remainingSeconds <= 10) {
        barClass += ' danger';
    } else if (remainingSeconds <= 30) {
        barClass += ' warning';
    }

    return (
        <div className="timer-bar-container">
            <div className={barClass} style={{ width: `${percentage}%` }}></div>
        </div>
    );
};

const ProgressChart = ({ historyData }) => {
    const chartData = historyData
        .filter(session => 
            session.mode === 'strict' &&
            session.analysis_report &&
            session.analysis_report.pillars
        )
        .map(session => {
            const pillars = session.analysis_report.pillars;
            return {
                date: new Date(session.timestamp).toLocaleDateString(),
                'Problem/Solution Fit': pillars['Problem/Solution Fit']?.score || 0,
                'Founder Conviction': pillars['Formidable Founders (Clarity & Conviction)']?.score || 0,
                'Market & Timing': pillars['Market / \'Why Now?\'']?.score || 0,
            };
        })
        .reverse(); 

    if (chartData.length < 2) {
        return <p style={{textAlign: 'center', color: 'var(--secondary-text)', padding: '40px 20px'}}>Complete at least two "Strict Pitch" sessions to see your progress chart here.</p>;
    }

    return (
        <div style={{height: 400}}>
            <h3 style={{textAlign: 'center', color: 'var(--primary-text)', marginBottom: '20px'}}>Your Pitching Skill Progression</h3>
            <ResponsiveContainer width="100%" height="100%">
                <LineChart
                    data={chartData}
                    margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                    <XAxis dataKey="date" tick={{ fill: 'var(--secondary-text)' }} />
                    <YAxis domain={[0, 5]} tick={{ fill: 'var(--secondary-text)' }} />
                    <Tooltip contentStyle={{ backgroundColor: 'var(--card-background)', border: '1px solid var(--border-color)'}} />
                    <Legend />
                    <Line type="monotone" dataKey="Problem/Solution Fit" stroke="#8884d8" activeDot={{ r: 8 }} />
                    <Line type="monotone" dataKey="Founder Conviction" stroke="#82ca9d" />
                    <Line type="monotone" dataKey="Market & Timing" stroke="#ffc658" />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
};


const StartupDetailsForm = ({ profiles, currentDetails, onDetailChange, onProfileChange, onManageProfiles }) => (
    <div className="content-card">
        <h2>1. Define Your Startup</h2>
        <div className="form-group">
            <label htmlFor="startupProfileSelect">Load Saved Profile:</label>
            <select id="startupProfileSelect" value={currentDetails.profileId || ''} onChange={onProfileChange}>
                <option value="">-- New Startup Profile --</option>
                {profiles.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
        </div>
        <div style={{ textAlign: 'center', margin: '20px 0' }}>
            <button onClick={onManageProfiles} className="btn btn-secondary">Manage Startup Profiles</button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="form-group">
                <label htmlFor="startupNameInput">Startup Name:</label>
                <input type="text" id="startupNameInput" placeholder="e.g., Golden Kitty Ventures" value={currentDetails.name} onChange={e => onDetailChange('name', e.target.value)} />
            </div>
            <div className="form-group">
                <label htmlFor="oneLinerInput">One-Sentence Pitch:</label>
                <textarea id="oneLinerInput" placeholder="We are building the 'Stripe' for cat treat subscriptions." value={currentDetails.pitch} onChange={e => onDetailChange('pitch', e.target.value)}></textarea>
            </div>
            <div className="form-group">
                <label htmlFor="coreProblemInput">Problem You Solve:</label>
                <textarea id="coreProblemInput" placeholder="Who has this problem and why is it painful?" value={currentDetails.problem} onChange={e => onDetailChange('problem', e.target.value)}></textarea>
            </div>
        </div>
    </div>
);

const ModeSelection = ({ selectedMode, onModeChange }) => (
    <div className="content-card">
        <h2>2. Choose Your Practice Mode</h2>
        <div className="mode-options">
            <div className="mode-option">
                <input type="radio" id="mode-strict" name="pitchMode" value="strict" checked={selectedMode === 'strict'} onChange={onModeChange} />
                <label htmlFor="mode-strict">
                    <strong>Strict Pitch</strong>
                    <div>A timed, high-pressure pitch session.</div>
                </label>
            </div>
            <div className="mode-option">
                <input type="radio" id="mode-drill" name="pitchMode" value="drill" checked={selectedMode === 'drill'} onChange={onModeChange} />
                 <label htmlFor="mode-drill">
                    <strong>Drill Mode</strong>
                    <div>A back-to-back Q&A with investors.</div>
                </label>
            </div>
        </div>
    </div>
);

const PitchControls = ({ appState, onStart, onAbort, isDisabled }) => {
    const getButtonText = () => {
        switch (appState) {
            case 'initial':
            case 'disconnected': return 'Connecting...';
            case 'ready_to_pitch': return 'Start Practice Session';
            case 'generating_report': return 'Generating Report...';
            default: return null;
        }
    };
    const text = getButtonText();
    return (
        <div className="controls-stream">
            {text && <button id="actionBtn" className="btn" onClick={onStart} disabled={isDisabled}>{text}</button>}
            {['listening', 'awaiting_confirmation', 'processing', 'processing_audio'].includes(appState) && <button id="stopBtn" className="btn btn-danger" style={{ display: 'inline-block' }} onClick={onAbort}>End Session</button>}
        </div>
    );
};


const Investor = ({ name, avatarSrc, isSpeaking }) => (
    <div className={`investor ${isSpeaking ? 'speaking' : ''}`}>
        <img src={avatarSrc} alt={name} className="avatar" />
        <div className="investor-name-title">{name}</div>
    </div>
);

const InvestorPanel = ({ speakingInvestor }) => (
    <div className="investor-panel">
        <Investor name="Alex Chen" avatarSrc="https://c4.wallpaperflare.com/wallpaper/840/637/166/anonymous-monochrome-suits-tie-wallpaper-preview.jpg" isSpeaking={speakingInvestor === 'Alex Chen'} />
        <Investor name="Maria Santos" avatarSrc="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTuxgWfhSffaZ_ZFi5MwXfdjhTpqfeEW76-UN8bz4VApX7B7HQf6yljb3CrkTNPuJXh6nU&usqp=CAU" isSpeaking={speakingInvestor === 'Maria Santos'} />
        <Investor name="Ben Carter" avatarSrc="https://w0.peakpx.com/wallpaper/419/972/HD-wallpaper-reborn-live-traje-black-suit-suits-tie.jpg" isSpeaking={speakingInvestor === 'Ben Carter'} />
    </div>
);

const UserSpeechArea = ({ transcription, onConfirm, onReset, showControls }) => (
    <div className="user-speech-area content-card">
        <h3>Your Response</h3>
        <p id="user-transcription">
            {transcription || 'Your transcribed response will appear here...'}
        </p>
        <div className="response-controls" style={{ display: showControls ? 'flex' : 'none' }}>
            <button id="resetBtn" className="control-btn" title="Reset and try again" onClick={onReset}>⟳</button>
            <button id="confirmBtn" className="control-btn" title="Confirm and send" onClick={onConfirm}>✓</button>
        </div>
    </div>
);

const ConversationLog = ({ log }) => {
    const logEndRef = useRef(null);
    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [log]);
    return (
        <div className="content-card">
            <h3>Full Conversation Log</h3>
            <div className="full-log-area">
                <div id="transcription">
                    {log.map((entry, index) => (
                        <div key={index} className={`transcription-entry ${entry.role === 'You' ? 'user-text-log' : ''}`}>
                            <span className={`investor-name-log investor-${(entry.role || '').toLowerCase().replace(/\s+/g, '-')}`}>
                                {entry.role}:
                            </span>
                            {' '}{entry.text}
                        </div>
                    ))}
                    <div ref={logEndRef} />
                </div>
            </div>
        </div>
    );
};

// ############################################################################
// ## THE MAIN PAGE COMPONENT
// ############################################################################

function PitchPracticePage() {
    const { currentUser } = useAuth();
    const [appState, setAppState] = useState('initial');
    const [statusMessage, setStatusMessage] = useState('Initializing...');
    const [conversationLog, setConversationLog] = useState([]);
    const [userTranscription, setUserTranscription] = useState('');
    const [speakingInvestor, setSpeakingInvestor] = useState(null);
    const [pitchMode, setPitchMode] = useState('strict');
    const [startupDetails, setStartupDetails] = useState({ profileId: '', name: '', pitch: '', problem: '' });
    const [savedProfiles, setSavedProfiles] = useState([]);
    const [reportData, setReportData] = useState(null);
    const [pitchTimer, setPitchTimer] = useState(PITCH_DURATION_SECONDS);
    const [activeTab, setActiveTab] = useState('setup');
    const [historyData, setHistoryData] = useState([]);

    const socketRef = useRef(null);
    const audioContextRef = useRef(null);
    const mediaStreamRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const masterRecorderRef = useRef(null);
    const processorNodeRef = useRef(null);
    const utteranceChunksRef = useRef([]);
    const pitchTimerIntervalRef = useRef(null);
    const userHasSpokenRef = useRef(false);
    const silenceTimerRef = useRef(null);
    const appStateRef = useRef(appState);
    const transcriptionRef = useRef(userTranscription);

    useEffect(() => {
        transcriptionRef.current = userTranscription;
    }, [userTranscription]);

    const setAndTrackAppState = useCallback((newState) => {
        appStateRef.current = newState;
        setAppState(newState);
    }, []);

    const cleanupAudio = useCallback(() => {
        if (pitchTimerIntervalRef.current) { clearInterval(pitchTimerIntervalRef.current); pitchTimerIntervalRef.current = null; }
        if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null; }
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") { mediaRecorderRef.current.stop(); }
        mediaRecorderRef.current = null;
        if (masterRecorderRef.current && masterRecorderRef.current.state === "recording") { masterRecorderRef.current.stop(); }
        masterRecorderRef.current = null;
        if (processorNodeRef.current) { processorNodeRef.current.disconnect(); processorNodeRef.current = null; }
        if (mediaStreamRef.current) { mediaStreamRef.current.getTracks().forEach(track => track.stop()); mediaStreamRef.current = null; }
        if (audioContextRef.current && audioContextRef.current.state !== 'closed') { audioContextRef.current.close().catch(console.error); }
        audioContextRef.current = null;
    }, []);

    const generateReport = useCallback((reason = 'user_ended') => {
        if (reason === 'user_aborted') {
            cleanupAudio();
            setReportData(null);
            setAndTrackAppState('ready_to_pitch');
            setStatusMessage('Ready. Select a mode and start your practice.');
            setConversationLog([]);
            setUserTranscription('');
            setActiveTab('setup');
            return;
        }

        if (appStateRef.current === 'generating_report') return;
        setAndTrackAppState('generating_report');
        setStatusMessage("Ending session... generating report...");

        const sendEndMessage = () => {
            if (socketRef.current?.readyState === WebSocket.OPEN) {
                const endSessionMessage = { type: "end_session", reason: reason };
                socketRef.current.send(JSON.stringify(endSessionMessage));
            } else {
                setAndTrackAppState('disconnected');
                setStatusMessage("Connection lost. Could not generate report.");
            }
        };

        if (masterRecorderRef.current?.state === "recording") {
            masterRecorderRef.current.onstop = sendEndMessage;
            masterRecorderRef.current.stop();
        } else {
            sendEndMessage();
        }
    }, [cleanupAudio, setAndTrackAppState]);

        // ** ROBUST useEffect for WebSocket connection **
    useEffect(() => {
        if (!currentUser || socketRef.current) {
            return; // Don't connect if no user or already connected
        }

        let isMounted = true;
        let localSocket = null;

        const connect = async () => {
            setAndTrackAppState('disconnected');
            setStatusMessage('Connecting...');
            
            try {
                const token = await currentUser.getIdToken(true);
                localSocket = new WebSocket(`${BACKEND_WS_URL}?token=${token}`);
                socketRef.current = localSocket;

                localSocket.onopen = () => {
                    if (isMounted) {
                        setAndTrackAppState('ready_to_pitch');
                        setStatusMessage('Ready. Select a mode and start your practice.');
                        localSocket.send(JSON.stringify({ type: "get_history" }));
                    }
                };

                localSocket.onmessage = (event) => {
                    if (!isMounted) return;
                    const messageData = JSON.parse(event.data);
                    
                    // The logic for handling messages remains the same
                    switch (messageData.type) {
                        case 'history_data': setHistoryData(messageData.data); break;
                        case 'analysis_report':
                            setReportData(messageData.data);
                            setAndTrackAppState('report_complete');
                            cleanupAudio();
                            localSocket.send(JSON.stringify({ type: "get_history" }));
                            break;
                        case 'session_terminated':
                             setAndTrackAppState('session_ended');
                             setStatusMessage(`SESSION ENDED: ${messageData.reason || "The investor has ended the meeting."}`);
                             setTimeout(() => generateReport('investor_terminated'), 2500);
                             break;
                        case 'user_interim_transcript':
                            if (appStateRef.current === 'processing_audio') {
                                setUserTranscription(messageData.text);
                                setAndTrackAppState('awaiting_confirmation');
                                setStatusMessage('Review your transcription and confirm.');
                            }
                            break;
                        case 'investor':
                             if (!['listening', 'processing'].includes(appStateRef.current)) return;
                             setConversationLog(prev => [...prev, { role: messageData.investor_name, text: messageData.text }]);
                             setSpeakingInvestor(messageData.investor_name);
                             setTimeout(() => setSpeakingInvestor(null), 7000);
                             userHasSpokenRef.current = false;
                             if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
                             silenceTimerRef.current = null;
                             setAndTrackAppState('listening');
                             setStatusMessage('Listening for your response...');
                             break;
                        case 'error':
                            setStatusMessage(`Error: ${messageData.text}`);
                            if (['processing', 'processing_audio'].includes(appStateRef.current)) {
                                setAndTrackAppState('listening');
                            }
                            break;
                        default: break;
                    }
                };
                
                localSocket.onclose = () => { 
                    if (isMounted) {
                        setStatusMessage('Disconnected. Refresh to reconnect.'); 
                        setAndTrackAppState('disconnected');
                        socketRef.current = null; 
                    }
                };
                
                localSocket.onerror = (error) => { 
                    console.error("WebSocket Error:", error); 
                    if (isMounted) localSocket.close(); 
                };

            } catch (error) {
                console.error("Auth token error for WebSocket:", error);
                if (isMounted) setStatusMessage('Authentication error. Cannot connect.');
            }
        };
        
        connect();

        return () => {
            isMounted = false;
            if (localSocket) {
                localSocket.close();
                socketRef.current = null;
            }
            cleanupAudio();
        };
    }, [currentUser, setAndTrackAppState, cleanupAudio, generateReport]); // Stable dependencies
    
    useEffect(() => {
        if (appState === 'listening' && pitchMode === 'strict') {
            pitchTimerIntervalRef.current = setInterval(() => {
                setPitchTimer(prev => {
                    if (prev <= 1) {
                        clearInterval(pitchTimerIntervalRef.current);
                        generateReport('timer_expired');
                        return 0;
                    }
                    return prev - 1;
                });
            }, 1000);
        } else {
            if (pitchTimerIntervalRef.current) {
                clearInterval(pitchTimerIntervalRef.current);
            }
        }
        return () => clearInterval(pitchTimerIntervalRef.current);
    }, [appState, pitchMode, generateReport]);

    useEffect(() => {
        if (!currentUser) return;
        const fetchAndSetInitialData = async () => {
            try {
                const token = await currentUser.getIdToken();
                const response = await fetch('http://localhost:8000/api/profiles', { headers: { 'Authorization': `Bearer ${token}` } });
                if (!response.ok) throw new Error('Failed to fetch profiles');
                const profiles = await response.json();
                setSavedProfiles(profiles);
                if (profiles.length > 0) {
                    const mostRecent = profiles[0];
                    setStartupDetails({ profileId: mostRecent.id, name: mostRecent.name, pitch: mostRecent.pitch, problem: mostRecent.problem, });
                } else {
                    const storedData = sessionStorage.getItem('deckAnalysisForPractice');
                    if (storedData) {
                        const analysis = JSON.parse(storedData);
                        setStartupDetails(prev => ({ ...prev, name: analysis.suggestedStartupName, pitch: analysis.suggestedOneLiner, problem: analysis.suggestedProblem }));
                        sessionStorage.removeItem('deckAnalysisForPractice');
                    }
                }
            } catch (error) { console.error("Error fetching initial data:", error); }
        };
        fetchAndSetInitialData();
    }, [currentUser]);

    const startInternalMediaRecorder = useCallback(() => {
        if (!mediaStreamRef.current || mediaRecorderRef.current?.state === 'recording') return;
        utteranceChunksRef.current = [];
        const recorder = new MediaRecorder(mediaStreamRef.current, { mimeType: 'audio/webm;codecs=opus' });
        mediaRecorderRef.current = recorder;
        recorder.ondataavailable = e => { if (e.data.size > 0) utteranceChunksRef.current.push(e.data); };
        recorder.onstop = () => {
            const audioBlob = new Blob(utteranceChunksRef.current, { type: 'audio/webm;codecs=opus' });
            if (audioBlob.size > 0 && socketRef.current?.readyState === WebSocket.OPEN) {
                socketRef.current.send(audioBlob);
            }
        };
        recorder.start();
    }, []);

    const initializeAudioProcessing = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaStreamRef.current = stream;
            const context = new (window.AudioContext || window.webkitAudioContext)();
            audioContextRef.current = context;
            if (context.state === 'suspended') await context.resume();
            const source = context.createMediaStreamSource(stream);
            const processor = context.createScriptProcessor(4096, 1, 1);
            processorNodeRef.current = processor;
            processor.onaudioprocess = (e) => {
                if (appStateRef.current !== 'listening') return;
                const buffer = e.inputBuffer.getChannelData(0);
                const rms = Math.sqrt(buffer.reduce((s, v) => s + v * v, 0) / buffer.length);
                const silenceThreshold = 0.01;
                const silenceDuration = 1500;
                if (!userHasSpokenRef.current && rms > 0.02) {
                    userHasSpokenRef.current = true;
                    startInternalMediaRecorder();
                    setStatusMessage("Recording your response...");
                    return;
                }
                if (userHasSpokenRef.current && mediaRecorderRef.current?.state === 'recording') {
                    if (rms < silenceThreshold) {
                        if (!silenceTimerRef.current) {
                            silenceTimerRef.current = setTimeout(() => {
                                setAndTrackAppState('processing_audio');
                                setStatusMessage('Processing your speech...');
                                if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
                                silenceTimerRef.current = null;
                            }, silenceDuration);
                        }
                    } else {
                        if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null; }
                    }
                }
            };
            source.connect(processor);
            processor.connect(context.destination);
            return true;
        } catch (err) {
            setStatusMessage(`Error accessing microphone: ${err.message}`);
            return false;
        }
    }, [setAndTrackAppState, startInternalMediaRecorder]);
    
    const saveOrUpdateProfile = useCallback(async () => {
        if (!currentUser) return startupDetails;
        const { name, pitch, problem, profileId } = startupDetails;
        if (!name || !pitch || !problem) {
            alert("Please fill out all startup details before starting.");
            return null;
        }
        try {
            const token = await currentUser.getIdToken();
            const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
            const payload = { name, pitch, problem };
            const url = profileId ? `http://localhost:8000/api/profiles/${profileId}` : 'http://localhost:8000/api/profiles';
            const method = profileId ? 'PUT' : 'POST';
            const response = await fetch(url, { method, headers, body: JSON.stringify(payload) });
            if (!response.ok) throw new Error(`Failed to save profile. Status: ${response.status}`);
            const savedProfile = await response.json();
            const newDetails = { profileId: savedProfile.id, name: savedProfile.name, pitch: savedProfile.pitch, problem: savedProfile.problem };
            setStartupDetails(newDetails);
            setSavedProfiles(prev => {
                const existing = prev.find(p => p.id === savedProfile.id);
                return existing ? prev.map(p => p.id === savedProfile.id ? savedProfile : p).sort((a, b) => new Date(b.lastUsed) - new Date(a.lastUsed)) : [savedProfile, ...prev];
            });
            return newDetails;
        } catch (error) {
            console.error("Failed to save profile:", error);
            alert("Could not save startup profile. Practice will start without saving.");
            return startupDetails;
        }
    }, [currentUser, startupDetails]);

    const handleStartPitch = useCallback(async () => {
        const detailsForSession = await saveOrUpdateProfile();
        if (!detailsForSession) return;
        if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
            setStatusMessage("Error: Connection not yet established. Please wait a moment.");
            return;
        }
        const audioInitialized = await initializeAudioProcessing();
        if (!audioInitialized) return;
        setConversationLog([]); setUserTranscription(''); setSpeakingInvestor(null);
        userHasSpokenRef.current = false;
        setPitchTimer(PITCH_DURATION_SECONDS);
        socketRef.current.send(JSON.stringify({ type: "startup_details", data: { ...detailsForSession, mode: pitchMode } }));
        masterRecorderRef.current = new MediaRecorder(mediaStreamRef.current, { mimeType: 'audio/webm;codecs=opus' });
        masterRecorderRef.current.start();
        if (pitchMode === 'strict') { setAndTrackAppState('listening'); setStatusMessage("Microphone active. Your pitch session has started!"); } 
        else { setAndTrackAppState('processing'); setStatusMessage("Drill Mode activated. Waiting for the first question..."); }
    }, [saveOrUpdateProfile, initializeAudioProcessing, pitchMode, setAndTrackAppState]);

    const handleConfirmResponse = useCallback(() => {
        setAndTrackAppState('processing');
        setStatusMessage("Investor is thinking...");
        setSpeakingInvestor(null);
        const textToSend = transcriptionRef.current.trim() || "[Silent Response]";
        setConversationLog(prev => [...prev, { role: 'You', text: textToSend }]);
        socketRef.current.send(JSON.stringify({ type: "send_composed_text", text: textToSend }));
        setUserTranscription('');
    }, [setAndTrackAppState]);
    
    const handleResetResponse = useCallback(() => {
        userHasSpokenRef.current = false;
        setUserTranscription('');
        if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
        setAndTrackAppState('listening');
        setStatusMessage("Your last response was cleared. Please try again.");
    }, [setAndTrackAppState]);
    
    const handleProfileChange = useCallback((e) => {
        const profileId = e.target.value;
        const profile = savedProfiles.find(p => p.id === profileId);
        if (profile) {
            setStartupDetails({ profileId: profile.id, name: profile.name, pitch: profile.pitch, problem: profile.problem });
        } else {
            setStartupDetails({ profileId: '', name: '', pitch: '', problem: '' });
        }
    }, [savedProfiles]);

    const resetForPractice = useCallback(() => {
        setReportData(null); 
        setAndTrackAppState('ready_to_pitch'); 
        setStatusMessage('Ready. Select a mode and start your practice.');
        setConversationLog([]); 
        setUserTranscription(''); 
        setActiveTab('setup');
    }, [setAndTrackAppState]);

    const renderContent = () => {
        if (appState === 'report_complete' && reportData) {
            return <ReportDisplay reportData={reportData} onPracticeAgain={resetForPractice} />;
        }
        if (['listening', 'awaiting_confirmation', 'processing', 'processing_audio', 'session_ended', 'generating_report'].includes(appState)) {
            return (
                <div id="pitchingArea">
                    <div className="content-card">
                        <h2>Boardroom</h2>
                        <InvestorPanel speakingInvestor={speakingInvestor} />
                    </div>
                    <div className="main-interaction-area" style={{display: 'flex', flexDirection: 'column', gap: '2rem'}}>
                        <UserSpeechArea transcription={userTranscription} onConfirm={handleConfirmResponse} onReset={handleResetResponse} showControls={appState === 'awaiting_confirmation'} />
                        <ConversationLog log={conversationLog} />
                    </div>
                </div>
            );
        }
        return (
            <>
                <header className="page-header">
                  <h1>Live Pitch Practice</h1>
                  <p>Step into the virtual boardroom. Face our AI investors, refine your pitch, and master your responses under pressure.</p>
                </header>
                <div className="tabs-container">
                    <button className={`tab-button ${activeTab === 'setup' ? 'active' : ''}`} onClick={() => setActiveTab('setup')}>Practice Setup</button>
                    <button className={`tab-button ${activeTab === 'progress' ? 'active' : ''}`} onClick={() => setActiveTab('progress')}>My Progress</button>
                </div>
                {activeTab === 'setup' ? (
                    <div className="tab-content">
                        <StartupDetailsForm profiles={savedProfiles} currentDetails={startupDetails} onDetailChange={(field, value) => setStartupDetails(prev => ({ ...prev, [field]: value }))} onProfileChange={handleProfileChange} onManageProfiles={() => alert('Manage Profiles feature coming soon!')} />
                        <ModeSelection selectedMode={pitchMode} onModeChange={e => setPitchMode(e.target.value)} />
                    </div>
                ) : (
                    <div className="tab-content content-card">
                        <ProgressChart historyData={historyData} />
                    </div>
                )}
            </>
        );
    };

    return (
        <div className="pitch-practice-container" style={{position: 'relative'}}>
            {['listening', 'awaiting_confirmation'].includes(appState) && pitchMode === 'strict' && <TimerBar remainingSeconds={pitchTimer} totalSeconds={PITCH_DURATION_SECONDS} />}
            <div id="status" className={statusMessage.includes('Error') || statusMessage.includes('ENDED') ? 'error' : ''}>
                {statusMessage || '...'}
            </div>
            
            {renderContent()}
            
            {(appState === 'ready_to_pitch' && activeTab === 'setup') && (
                 <PitchControls appState={appState} onStart={handleStartPitch} isDisabled={!startupDetails.name || !startupDetails.pitch} />
            )}
            {['listening', 'awaiting_confirmation', 'processing', 'processing_audio', 'generating_report'].includes(appState) && (
                <PitchControls appState={appState} onStart={handleStartPitch} onAbort={() => generateReport('user_aborted')} isDisabled={appState === 'generating_report'} />
            )}
        </div>
    );
}

export default PitchPracticePage;
