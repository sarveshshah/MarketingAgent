import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { MessageSquare, FileText, Settings, Send, Play, RefreshCw, Download } from 'lucide-react';

/**
 * MarketingAgent Component
 * 
 * This component serves as the frontend for the Marketing Strategy Generator.
 * It maps user inputs to the placeholders defined in 'markdown_formatting_prompt.txt'.
 */

const MarketingAgent = () => {
  // ---------------------------------------------------------------------------
  // State Management
  // ---------------------------------------------------------------------------
  const [activeTab, setActiveTab] = useState('form'); // 'form' or 'chat'
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedReport, setGeneratedReport] = useState('');
  
  // Form State - Maps directly to placeholders in your prompt file
  const [formData, setFormData] = useState({
    campaign_type: 'Product Launch',
    target_industry: 'SaaS / Tech',
    budget: '$50,000',
    timeline: 'Q3 2024',
    goals: 'Acquire 1,000 new users; 20% conversion rate.',
    past_campaign_insights: 'Previous email campaigns had low open rates.',
    market_trends: 'Shift towards video content on LinkedIn.',
    target_audience: 'CTOs and VP of Engineering at mid-sized startups.',
    campaign_channels: 'LinkedIn, Email, Twitter',
    acquisition_cost_estimate: '$150',
    expected_roi: '3.5x',
    primary_channels: 'LinkedIn (60%), Email (40%)',
    channel_rationale: 'High engagement for B2B decision makers on LinkedIn.',
    expected_reach: '500k Impressions',
    channel_breakdown: '$30k LinkedIn, $20k Content Production',
    timeline_phases: 'Phase 1: Awareness (Weeks 1-4), Phase 2: Conversion (Weeks 5-8)',
    contingency_plan: 'Shift budget to Google Ads if LinkedIn CPC spikes.',
    identified_risks: 'Ad fatigue, low click-through rates.',
    mitigation_strategies: 'Refresh creative every 2 weeks.',
    success_metrics: 'CTR > 1.5%, CPA < $150'
  });

  // Chat State
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([
    { role: 'system', content: 'Hello! Fill out the form to generate a report, or ask me questions to help refine your strategy.' }
  ]);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------
  
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleGenerate = async () => {
    setIsGenerating(true);
    setActiveTab('chat'); // Switch to chat to show progress or results
    
    try {
      const response = await fetch('http://localhost:8000/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      
      if (!response.ok) throw new Error('Failed to generate report');
      
      const data = await response.json();
      setGeneratedReport(data.report);
      setChatHistory(prev => [...prev, { role: 'system', content: 'Report generated successfully! You can now ask me to refine specific sections.' }]);
    } catch (error) {
      console.error('Error:', error);
      setChatHistory(prev => [...prev, { role: 'system', content: 'Error connecting to the agent. Please ensure the backend is running.' }]);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleChatSubmit = (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userMsg = { role: 'user', content: chatInput };
    setChatHistory(prev => [...prev, userMsg]);
    setChatInput('');
    setIsGenerating(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_report: generatedReport,
          user_message: userMsg.content,
          chat_history: chatHistory
        }),
      });

      if (!response.ok) throw new Error('Failed to update report');

      const data = await response.json();
      setGeneratedReport(data.report);
      const agentMsg = { role: 'system', content: data.agent_message };
      setChatHistory(prev => [...prev, agentMsg]);
    } catch (error) {
      console.error('Error:', error);
      setChatHistory(prev => [...prev, { role: 'system', content: 'Error updating the report.' }]);
    } finally {
      setIsGenerating(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Render Helpers
  // ---------------------------------------------------------------------------

  const renderInputField = (label, name, type = "text") => (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {type === "textarea" ? (
        <textarea
          name={name}
          value={formData[name]}
          onChange={handleInputChange}
          className="w-full p-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          rows={3}
        />
      ) : (
        <input
          type="text"
          name={name}
          value={formData[name]}
          onChange={handleInputChange}
          className="w-full p-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      )}
    </div>
  );

  return (
    <div className="flex h-screen bg-gray-50 font-sans">
      {/* LEFT PANEL: Controls & Chat */}
      <div className="w-1/3 min-w-[400px] flex flex-col border-r border-gray-200 bg-white shadow-sm">
        
        {/* Header */}
        <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-gray-50">
          <h1 className="font-bold text-lg text-gray-800 flex items-center gap-2">
            <Settings className="w-5 h-5 text-blue-600" />
            Marketing Agent
          </h1>
          <div className="flex bg-gray-200 rounded-lg p-1">
            <button
              onClick={() => setActiveTab('form')}
              className={`px-3 py-1 text-sm rounded-md transition-all ${activeTab === 'form' ? 'bg-white shadow text-blue-600 font-medium' : 'text-gray-600 hover:text-gray-900'}`}
            >
              Data Input
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-3 py-1 text-sm rounded-md transition-all ${activeTab === 'chat' ? 'bg-white shadow text-blue-600 font-medium' : 'text-gray-600 hover:text-gray-900'}`}
            >
              Assistant
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-4">
          
          {/* FORM VIEW */}
          {activeTab === 'form' && (
            <div className="space-y-6">
              <div className="bg-blue-50 p-3 rounded-md border border-blue-100 text-sm text-blue-800 mb-4">
                Fill in the raw components below. The agent will synthesize this into a professional report.
              </div>

              <section>
                <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2"><FileText className="w-4 h-4"/> 1. Campaign Overview</h3>
                {renderInputField("Campaign Type", "campaign_type")}
                {renderInputField("Target Industry", "target_industry")}
                {renderInputField("Budget", "budget")}
                {renderInputField("Timeline", "timeline")}
                {renderInputField("Goals", "goals", "textarea")}
              </section>

              <section>
                <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2"><FileText className="w-4 h-4"/> 2. Strategy & Data</h3>
                {renderInputField("Past Insights", "past_campaign_insights", "textarea")}
                {renderInputField("Market Trends", "market_trends", "textarea")}
                {renderInputField("Target Audience", "target_audience", "textarea")}
              </section>

              <section>
                <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2"><FileText className="w-4 h-4"/> 3. Execution Plan</h3>
                {renderInputField("Primary Channels", "primary_channels")}
                {renderInputField("Timeline Phases", "timeline_phases", "textarea")}
                {renderInputField("Risks", "identified_risks", "textarea")}
                {renderInputField("Mitigation", "mitigation_strategies", "textarea")}
              </section>

              <button
                onClick={handleGenerate}
                disabled={isGenerating}
                className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center justify-center gap-2 transition-colors shadow-sm"
              >
                {isGenerating ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                Generate Strategy Report
              </button>
            </div>
          )}

          {/* CHAT VIEW */}
          {activeTab === 'chat' && (
            <div className="flex flex-col h-full">
              <div className="flex-1 space-y-4 mb-4">
                {chatHistory.map((msg, idx) => (
                  <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] p-3 rounded-lg text-sm ${
                      msg.role === 'user' 
                        ? 'bg-blue-600 text-white rounded-br-none' 
                        : 'bg-gray-100 text-gray-800 rounded-bl-none border border-gray-200'
                    }`}>
                      {msg.content}
                    </div>
                  </div>
                ))}
                {isGenerating && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 p-3 rounded-lg rounded-bl-none text-sm text-gray-500 italic flex items-center gap-2">
                      <RefreshCw className="w-3 h-3 animate-spin" /> Agent is thinking...
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Chat Input Area (Always visible if in Chat mode) */}
        {activeTab === 'chat' && (
          <div className="p-4 border-t border-gray-200 bg-white">
            <form onSubmit={handleChatSubmit} className="flex gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask to refine the report (e.g., 'Make the tone more formal')..."
                className="flex-1 p-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
              <button 
                type="submit"
                disabled={isGenerating || !chatInput.trim()}
                className="p-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        )}
      </div>

      {/* RIGHT PANEL: Report Preview */}
      <div className="flex-1 flex flex-col bg-gray-100 h-full overflow-hidden">
        {/* Toolbar */}
        <div className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 shadow-sm z-10">
          <h2 className="font-semibold text-gray-700 flex items-center gap-2">
            <FileText className="w-5 h-5 text-gray-500" />
            Report Preview
          </h2>
          <div className="flex gap-2">
             <button className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-md border border-gray-300 transition-colors">
              <Download className="w-4 h-4" /> Export Markdown
            </button>
          </div>
        </div>

        {/* Markdown Content */}
        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-4xl mx-auto bg-white shadow-lg rounded-xl min-h-[800px] p-10 border border-gray-200">
            {generatedReport ? (
              <article className="prose prose-slate max-w-none prose-headings:font-bold prose-h1:text-3xl prose-h1:text-blue-900 prose-h2:text-xl prose-h2:text-blue-800 prose-h2:border-b prose-h2:pb-2 prose-h2:mt-8 prose-table:border-collapse prose-th:bg-gray-100 prose-th:p-2 prose-td:p-2 prose-td:border">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {generatedReport}
                </ReactMarkdown>
              </article>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-gray-400">
                <FileText className="w-16 h-16 mb-4 opacity-20" />
                <p className="text-lg font-medium">No report generated yet</p>
                <p className="text-sm">Fill out the form on the left and click "Generate"</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MarketingAgent;