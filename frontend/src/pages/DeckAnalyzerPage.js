// File: frontend/src/pages/DeckAnalyzerPage.js

import React, { useState, useEffect, useRef } from 'react';
import '../App.css'; // Use the main App.css file
import { marked } from 'marked';
const BACKEND_HTTP_URL = process.env.REACT_APP_BACKEND_URL || 'http://127.0.0.1:8000';

const StatusBadge = ({ status }) => {
  const statusClass = status ? status.toLowerCase() : '';
  return <span className={`status ${statusClass}`}>{status}</span>;
};

const ChatWidget = ({ messages, onSendMessage, topic, onClose }) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const handleSend = () => {
    if (input.trim()) {
      onSendMessage(input, topic);
      setInput('');
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === 'Enter') {
      handleSend();
    }
  };

  return (
    <div className="chat-widget">
      <div className="chat-header">
        The Catalyst
        <button onClick={onClose} style={{float: 'right', background: 'none', border: 'none', color: 'var(--secondary-text)', fontSize: '1.5rem', cursor: 'pointer', lineHeight: 1}}>×</button>
      </div>
      <div className="chat-messages">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.author}-message`}>
            <div
              className="message-bubble"
              dangerouslySetInnerHTML={{ __html: marked.parse(msg.text) }}
            >
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className="chat-input">
        <input 
          type="text" 
          value={input} 
          onChange={(e) => setInput(e.target.value)} 
          onKeyPress={handleKeyPress}
          placeholder="Ask a question..."
        />
        <button onClick={handleSend}>↑</button>
      </div>
    </div>
  );
};

function DeckAnalyzerPage() {
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
  const [file, setFile] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // Chat state
  const [chatMessages, setChatMessages] = useState([]);
  const [isChatVisible, setIsChatVisible] = useState(false);
  const [currentChatTopic, setCurrentChatTopic] = useState('General');

  const handleFileChange = (event) => {
    setFile(event.target.files[0]);
    setAnalysisResult(null);
    setError('');
    setIsChatVisible(false);
    setChatMessages([]);
  };
  
  const sendChatMessage = async (newMessageText, topic) => {
    const newUserMessage = { author: 'user', text: newMessageText };
    const updatedHistory = [...chatMessages, newUserMessage];
    setChatMessages(updatedHistory);
    setCurrentChatTopic(topic);

    try {
      const payload = { 
        history: updatedHistory, 
        topic: topic, 
        analysis: analysisResult 
      };
      
      const response = await fetch(`${BACKEND_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error);
      
      const aiReply = { author: 'ai', text: data.reply };
      setChatMessages([...updatedHistory, aiReply]);
    } catch (err) {
      const errorReply = { author: 'ai', text: `Sorry, I had trouble connecting. ${err.message}` };
      setChatMessages([...updatedHistory, errorReply]);
    }
  };

  const handleDiscussClick = (item) => {
    const topic = item.criterion;
    const initialMessage = `Let's talk about the "${topic}" section.`;
    if (!isChatVisible) setIsChatVisible(true);

    const initialAiMessage = { author: 'ai', text: analysisResult.initialChatMessage };
    const userClickMessage = { author: 'user', text: initialMessage };
    const newChatHistory = [initialAiMessage, userClickMessage];
    
    setChatMessages(newChatHistory);
    setCurrentChatTopic(topic);

    const sendInitialChat = async () => {
        try {
            const payload = { history: newChatHistory, topic: topic, analysis: analysisResult };
            const response = await fetch(`${BACKEND_URL}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error);
            const aiReply = { author: 'ai', text: data.reply };
            setChatMessages([...newChatHistory, aiReply]);
        } catch (err) {
            const errorReply = { author: 'ai', text: `Sorry, I had trouble connecting. ${err.message}` };
            setChatMessages([...newChatHistory, errorReply]);
        }
    };
    sendInitialChat();
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!file) {
      setError('Please select a pitch deck file to analyze.');
      return;
    }

    setIsLoading(true);
    setError('');
    setAnalysisResult(null);
    setIsChatVisible(false);

    const formData = new FormData();
    formData.append('pitchDeck', file);

    try {
      const response = await fetch(`${BACKEND_URL}/api/analyze`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'An unknown error occurred.');
      
      setAnalysisResult(data);
      
      // --- MODIFIED: Store deck text along with other info ---
      if (data.suggestedOneLiner && data.suggestedProblem && data.suggestedStartupName) {
        const practiceData = {
          suggestedStartupName: data.suggestedStartupName,
          suggestedOneLiner: data.suggestedOneLiner,
          suggestedProblem: data.suggestedProblem,
          deckText: data.deckText, // Pass the full deck text
        };
        sessionStorage.setItem('deckAnalysisForPractice', JSON.stringify(practiceData));
      }

      if (data.initialChatMessage) {
        setChatMessages([{ author: 'ai', text: data.initialChatMessage }]);
        setIsChatVisible(true);
      }

    } catch (err)
 {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container">
      <header className="page-header">
        <h1>Pitch Deck Analyzer</h1>
        <p>Upload your deck to get an instant, AI-powered analysis.</p>
      </header>

      <div className="upload-section content-card">
        <form onSubmit={handleSubmit}>
          <input type="file" accept=".pdf" onChange={handleFileChange} />
          <button type="submit" disabled={isLoading || !file} className="btn">
            {isLoading ? 'Analyzing...' : 'Analyze Deck'}
          </button>
        </form>
        {error && <p className="error-message">{error}</p>}
      </div>

      {isLoading && <div className="loader"></div>}

      {analysisResult && (
        <div id="results-section">
          <div className="content-card scorecard">
             <div className="score">
                <h3>Pitch Deck Score</h3>
                <div className="value deck-score">{analysisResult.pitchDeckScore}/10</div>
            </div>
            <div className="score">
                <h3>Company Potential</h3>
                <div className="value potential-score">{analysisResult.companyPotentialScore}/10</div>
            </div>
             <div className="score">
                <h3>Verdict</h3>
                <div className="verdict">{analysisResult.investorReadinessVerdict}</div>
            </div>
          </div>
          <div className="content-card checklist">
              <h3>Actionable Revision Checklist</h3>
              <ul>
                {analysisResult.actionableChecklist.map((item, index) => (
                  <li key={index} className={item.isCritical ? 'critical' : ''}>
                    {item.task}
                  </li>
                ))}
              </ul>
            </div>
          <div id="criteria-breakdown">
            {analysisResult.criteriaAnalysis.map((item, index) => (
              <div className="content-card criteria-card" key={index}>
                <div className="criteria-header">
                  <h4>{item.criterion}</h4>
                  <StatusBadge status={item.status} />
                </div>
                <div className="analysis-section">
                  <h5>Analysis</h5>
                  <p>{item.analysis}</p>
                  <h5>Investor's Take</h5>
                  <blockquote>{item.investorTake}</blockquote>
                  <button className="btn btn-secondary" onClick={() => handleDiscussClick(item)} style={{marginTop: '1rem'}}>
                    Discuss with AI Coach
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {isChatVisible && (
        <ChatWidget 
          messages={chatMessages}
          onSendMessage={sendChatMessage}
          topic={currentChatTopic}
          onClose={() => setIsChatVisible(false)}
        />
      )}
    </div>
  );
}

export default DeckAnalyzerPage;
