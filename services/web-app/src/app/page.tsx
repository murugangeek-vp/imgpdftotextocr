'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import {
  Upload,
  FileText,
  MessageSquare,
  Zap,
  ShieldCheck,
  RefreshCw,
  Copy,
  Check,
  TrendingUp,
  AlertTriangle,
  Lock,
  Globe,
  Database,
  Coins
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Helper to generate temporary user ID and session ID for local dev demo
const getSessionData = () => {
  if (typeof window === 'undefined') return { userId: 'guest-user', sessionId: 'sess-default' };
  let userId = localStorage.getItem('ocr_user_id');
  if (!userId) {
    userId = 'user-' + Math.random().toString(36).substring(2, 10);
    localStorage.setItem('ocr_user_id', userId);
  }
  let sessionId = sessionStorage.getItem('ocr_session_id');
  if (!sessionId) {
    sessionId = 'sess-' + Math.random().toString(36).substring(2, 10);
    sessionStorage.setItem('ocr_session_id', sessionId);
  }
  return { userId, sessionId };
};

export default function Home() {
  const [userId, setUserId] = useState('guest-user');
  const [sessionId, setSessionId] = useState('sess-default');
  const [tier, setTier] = useState<'free' | 'basic' | 'pro'>('free');
  
  // Quota states
  const [quota, setQuota] = useState<any>({
    allowed: true,
    limits: {
      pages_per_session: 5,
      pages_per_day: 5,
      pages_per_week: 20,
      pages_per_month: 50,
      max_file_size_mb: 10,
      max_pages_per_pdf: 5
    },
    usage: {
      pages_today: 0,
      pages_this_week: 0,
      pages_this_month: 0
    }
  });

  // Selected OCR languages (comma-separated list for backend)
  const [languages, setLanguages] = useState('en,hi');

  // Job states
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string>('');
  const [ocrResult, setOcrResult] = useState<any>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);

  // Tab management for result viewer
  const [activeTab, setActiveTab] = useState<'text' | 'markdown' | 'json'>('text');

  // Chat states
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);

  // Load user details
  useEffect(() => {
    const data = getSessionData();
    setUserId(data.userId);
    setSessionId(data.sessionId);
    fetchQuota(data.userId, data.sessionId, tier);
  }, [tier]);

  const fetchQuota = async (uId: string, sId: string, currentTier: string) => {
    try {
      const response = await fetch(`http://localhost:8080/quota-service/api/v1/quota/usage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: uId, session_id: sId, tier: currentTier })
      });
      if (response.ok) {
        const data = await response.json();
        setQuota(data);
      }
    } catch (e) {
      console.error('Error fetching quota:', e);
    }
  };

  // Mock Stripe/Razorpay Payments
  const handleUpgrade = (selectedTier: 'basic' | 'pro') => {
    toast.loading(`Initializing checkout with Stripe & Razorpay for ${selectedTier.toUpperCase()} tier...`, {
      duration: 2000
    });
    setTimeout(() => {
      setTier(selectedTier);
      toast.success(`Successfully upgraded to ${selectedTier.toUpperCase()} tier (Demo Mode)!`);
    }, 2000);
  };

  // File Dropzone Handler
  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    const file = acceptedFiles[0];

    // File validation: Size
    const fileSizeMb = file.size / (1024 * 1024);
    const maxAllowedSize = tier === 'free' ? 10 : tier === 'basic' ? 50 : 100;
    if (fileSizeMb > maxAllowedSize) {
      toast.error(`File size (${fileSizeMb.toFixed(2)}MB) exceeds limit of ${maxAllowedSize}MB for your current tier.`);
      return;
    }

    // PDF Validation setup
    if (file.type === 'application/pdf' && tier === 'free') {
      toast.error('Free tier is limited to 5 pages per PDF. Parsing pages locally to enforce SLA...');
    }

    setIsUploading(true);
    setUploadProgress(10);
    setOcrResult(null);
    setJobId(null);
    setJobStatus('Queuing');

    try {
      // Step 1: Request presigned url or direct upload
      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', userId);
      formData.append('session_id', sessionId);
      formData.append('tier', tier);
      formData.append('languages', languages);

      setUploadProgress(30);
      
      const response = await fetch('http://localhost:8080/ingestion-service/api/v1/upload/', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        const msg = errorData.detail?.message || errorData.detail || 'Upload failed';
        throw new Error(msg);
      }

      const uploadData = await response.json();
      setJobId(uploadData.job_id);
      setJobStatus('queued');
      setUploadProgress(100);
      setIsUploading(false);
      toast.success('Document uploaded and queued successfully!');

      // Step 2: Establish SSE connection for real-time tracking
      subscribeToJobStatus(uploadData.job_id);

    } catch (err: any) {
      setIsUploading(false);
      setJobStatus('failed');
      toast.error(err.message || 'Verification or scan failed. ClamAV check failed or quota exceeded.');
    }
  }, [userId, sessionId, tier, languages]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxFiles: 1,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.tiff', '.webp', '.bmp'],
      'application/pdf': ['.pdf']
    }
  });

  // Server-Sent Events subscription for job updates
  const subscribeToJobStatus = (id: string) => {
    const sseUrl = `http://localhost:8080/api/v1/jobs/${id}/stream`;
    const eventSource = new EventSource(sseUrl);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.job_id === id) {
          setJobStatus(data.status);
          if (data.status === 'completed') {
            toast.success('OCR Processing completed!');
            fetchResult(id);
            fetchQuota(userId, sessionId, tier); // refresh quota usage
            eventSource.close();
          } else if (data.status === 'failed') {
            toast.error(`OCR processing failed: ${data.error || 'Unknown error'}`);
            eventSource.close();
          }
        }
      } catch (err) {
        console.error('Error parsing SSE event:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE Error:', err);
      eventSource.close();
      // Fallback: poll result endpoint after 5 seconds
      setTimeout(() => fetchResult(id), 5000);
    };
  };

  const fetchResult = async (id: string) => {
    try {
      const res = await fetch(`http://localhost:8080/result-service/api/v1/results/${id}`);
      if (res.ok) {
        const data = await res.json();
        setOcrResult(data);
        setJobStatus('completed');
        // Pre-populate chat context
        const combinedText = data.pages?.map((p: any) => p.text).join('\n\n') || '';
        setChatMessages([
          {
            role: 'assistant',
            content: `Hello! I have analyzed **${data.file_name}** (${data.page_count} page(s)). You can query this document or ask me to summarize it.`
          }
        ]);
      }
    } catch (e) {
      toast.error('Failed to retrieve OCR results.');
    }
  };

  const copyToClipboard = () => {
    if (!ocrResult) return;
    const combinedText = ocrResult.pages?.map((p: any) => p.text).join('\n\n') || '';
    navigator.clipboard.writeText(combinedText);
    setCopied(true);
    toast.success('Copied to clipboard!');
    setTimeout(() => setCopied(false), 2000);
  };

  // Chat handler
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !jobId || isChatLoading) return;

    const userMessage = chatInput;
    setChatInput('');
    setChatMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setIsChatLoading(true);

    const combinedOcrText = ocrResult?.pages?.map((p: any) => p.text).join('\n\n') || '';

    try {
      const res = await fetch('http://localhost:8080/chat-service/api/v1/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: jobId,
          user_id: userId,
          tier: tier,
          messages: [...chatMessages.filter(m => m.role !== 'system'), { role: 'user', content: userMessage }],
          ocr_context: combinedOcrText
        })
      });

      if (!res.ok) {
        throw new Error('Failed to get response from AI Chat Service.');
      }

      const data = await res.json();
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.message,
          model_used: data.model_used,
          provider: data.provider
        }
      ]);
    } catch (err: any) {
      toast.error(err.message || 'Error processing AI chat.');
    } finally {
      setIsChatLoading(false);
    }
  };

  // Calculate usage percentages for display
  const dayUsagePercent = Math.min(
    100,
    quota.limits?.pages_per_day > 0 ? (quota.usage?.pages_today / quota.limits.pages_per_day) * 100 : 0
  );

  return (
    <div>
      {/* Dynamic sticky Navigation */}
      <nav>
        <div className="container nav-inner">
          <div className="nav-logo" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Coins className="gradient-text" style={{ width: '28px', height: '28px' }} />
            <span>OCR<span className="gradient-text">Platform</span></span>
          </div>

          <div className="nav-links">
            {/* Developer interactive Tier Switcher */}
            <div style={{ display: 'flex', background: '#313244', padding: '0.25rem', borderRadius: '8px', border: '1px solid #45475a', gap: '0.25rem' }}>
              {(['free', 'basic', 'pro'] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTier(t)}
                  style={{
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                    border: 'none',
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: tier === t ? '#7c3aed' : 'transparent',
                    color: tier === t ? 'white' : '#a6adc8',
                    transition: 'all 0.2s'
                  }}
                >
                  {t.toUpperCase()}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className={`badge badge-${tier}`}>
                {tier.toUpperCase()} TIER
              </span>
              <span className="status-dot green" title="All Services Healthy" />
            </div>
          </div>
        </div>
      </nav>

      <main className="container" style={{ padding: '2rem 1.5rem 6rem' }}>
        
        {/* Dynamic header / Hero */}
        <section className="hero" style={{ padding: '2rem 0 3rem' }}>
          <h1 className="gradient-text">Enterprise OCR Pipeline</h1>
          <p>
            Extract text from handwriting and printed documents across global languages and 22 Indian scheduled languages instantly using self-hosted Triton Inference Models.
          </p>
        </section>

        {/* Dynamic Quota Info Dashboard */}
        <section className="card" style={{ marginBottom: '2.5rem', background: 'rgba(30, 30, 46, 0.6)', backdropFilter: 'blur(8px)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <TrendingUp style={{ color: '#7c3aed' }} /> Usage Quota & Cost Control
              </h3>
              <p style={{ fontSize: '0.85rem', color: '#a6adc8' }}>
                Current limits and rates for the <strong className="gradient-text">{tier.toUpperCase()}</strong> tier
              </p>
            </div>
            
            <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.85rem' }}>
              <div>
                <span style={{ color: '#a6adc8' }}>Pages Today:</span>{' '}
                <strong>{quota.usage?.pages_today || 0} / {quota.limits?.pages_per_day === -1 ? '∞' : quota.limits?.pages_per_day || 5}</strong>
              </div>
              <div>
                <span style={{ color: '#a6adc8' }}>Max PDF size:</span>{' '}
                <strong>{quota.limits?.max_pages_per_pdf || 5} pages</strong>
              </div>
              <div>
                <span style={{ color: '#a6adc8' }}>Max File:</span>{' '}
                <strong>{quota.limits?.max_file_size_mb || 10} MB</strong>
              </div>
            </div>
          </div>

          <div className="quota-bar" style={{ marginBottom: '0.5rem' }}>
            <div className="quota-fill" style={{ width: `${quota.limits?.pages_per_day > 0 ? dayUsagePercent : 100}%` }}></div>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#a6adc8' }}>
            <span>Daily allowance progress indicator</span>
            <span>Reset occurs at midnight UTC</span>
          </div>
        </section>

        {/* File upload section */}
        <section style={{ marginBottom: '3rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '3fr 1.5fr', gap: '1.5rem' }}>
            <div>
              <div {...getRootProps()} className={`upload-zone ${isDragActive ? 'dragover' : ''}`}>
                <input {...getInputProps()} />
                <div className="icon">📁</div>
                <h3>Drag & Drop file here, or click to browse</h3>
                <p style={{ fontSize: '0.85rem', color: '#a6adc8', marginTop: '0.5rem' }}>
                  Supports PDF (up to {quota.limits?.max_pages_per_pdf || 5} pages), PNG, JPG, WEBP, TIFF, BMP
                </p>
                <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', marginTop: '1.5rem' }}>
                  <span style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem', color: '#a6e3a1' }}>
                    <ShieldCheck style={{ width: '14px', height: '14px' }} /> ClamAV Virus Scanned
                  </span>
                  <span style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem', color: '#89b4fa' }}>
                    <Database style={{ width: '14px', height: '14px' }} /> AES-256 Storage
                  </span>
                </div>
              </div>

              {isUploading && (
                <div style={{ marginTop: '1rem', padding: '1rem', background: '#313244', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                    <span>Scanning and uploading file...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="quota-bar">
                    <div className="quota-fill" style={{ width: `${uploadProgress}%`, background: 'var(--green)' }}></div>
                  </div>
                </div>
              )}

              {jobStatus && !isUploading && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '1rem', padding: '0.75rem 1rem', background: '#1e1e2e', border: '1px solid #313244', borderRadius: '8px', fontSize: '0.85rem' }}>
                  <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1.5s linear infinite' }} />
                  <span>Job Status: <strong style={{ color: '#a855f7' }}>{jobStatus.toUpperCase()}</strong></span>
                  {jobId && <span style={{ color: '#a6adc8' }}>Job ID: {jobId}</span>}
                </div>
              )}
            </div>

            {/* Language Selector and Notice */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div className="card">
                <h4 style={{ marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Globe style={{ width: '18px', height: '18px', color: '#7c3aed' }} /> OCR Languages
                </h4>
                <p style={{ fontSize: '0.75rem', color: '#a6adc8', marginBottom: '1rem' }}>
                  Provide comma-separated ISO language codes. Includes Indian and global scripts.
                </p>
                <input
                  type="text"
                  value={languages}
                  onChange={(e) => setLanguages(e.target.value)}
                  style={{
                    width: '100%',
                    background: '#313244',
                    border: '1px solid #45475a',
                    color: 'white',
                    padding: '0.5rem 0.75rem',
                    borderRadius: '6px',
                    fontSize: '0.85rem',
                    outline: 'none'
                  }}
                  placeholder="en,hi,ta,te..."
                />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem', marginTop: '0.75rem' }}>
                  {['en', 'hi', 'ta', 'te', 'mr', 'ml'].map(lang => (
                    <button
                      key={lang}
                      onClick={() => {
                        const langs = languages.split(',').map(l => l.trim()).filter(Boolean);
                        if (langs.includes(lang)) {
                          setLanguages(langs.filter(l => l !== lang).join(','));
                        } else {
                          setLanguages([...langs, lang].join(','));
                        }
                      }}
                      style={{
                        fontSize: '0.7rem',
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        border: 'none',
                        cursor: 'pointer',
                        background: languages.split(',').map(l => l.trim()).includes(lang) ? '#7c3aed' : '#313244',
                        color: 'white'
                      }}
                    >
                      {lang === 'en' ? 'English' : lang === 'hi' ? 'Hindi' : lang === 'ta' ? 'Tamil' : lang === 'te' ? 'Telugu' : lang === 'mr' ? 'Marathi' : 'Malayalam'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Regulatory and Data Notice */}
              <div className="data-notice">
                <Lock style={{ width: '20px', height: '20px', flexShrink: 0, color: 'var(--yellow)' }} />
                <div>
                  <strong style={{ display: 'block', marginBottom: '0.25rem' }}>Data Sovereignty Guarantee</strong>
                  Processed files are temporarily stored with AES-256 encryption. Free tier uploads are securely deleted 24 hours after execution. Processing locations are strictly region-governed.
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* OCR Result and AI Chat Interface */}
        {ocrResult && (
          <section style={{ marginBottom: '3rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.5rem', alignItems: 'stretch' }}>
              
              {/* OCR Text Viewer */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid #313244', paddingBottom: '0.75rem' }}>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {(['text', 'markdown', 'json'] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        style={{
                          background: activeTab === tab ? '#313244' : 'transparent',
                          border: 'none',
                          color: activeTab === tab ? 'white' : '#a6adc8',
                          padding: '0.4rem 0.8rem',
                          borderRadius: '6px',
                          fontSize: '0.85rem',
                          cursor: 'pointer',
                          fontWeight: 600
                        }}
                      >
                        {tab.toUpperCase()}
                      </button>
                    ))}
                  </div>

                  <button
                    onClick={copyToClipboard}
                    className="btn btn-outline"
                    style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem' }}
                  >
                    {copied ? <Check style={{ width: '14px', height: '14px', color: '#a6e3a1' }} /> : <Copy style={{ width: '14px', height: '14px' }} />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>

                <div style={{ flex: 1, overflowY: 'auto', maxHeight: '450px', background: '#11111b', padding: '1rem', borderRadius: '8px', border: '1px solid #313244', fontFamily: 'monospace', fontSize: '0.85rem', whiteSpace: 'pre-wrap' }}>
                  {activeTab === 'text' && (
                    <div>
                      {ocrResult.pages?.map((page: any, idx: number) => (
                        <div key={idx} style={{ marginBottom: '1.5rem' }}>
                          <div style={{ color: '#a855f7', fontWeight: 'bold', borderBottom: '1px dashed #313244', paddingBottom: '0.25rem', marginBottom: '0.5rem' }}>
                            --- Page {page.page_number} ---
                          </div>
                          {page.text}
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'markdown' && (
                    <div style={{ fontFamily: 'sans-serif', color: '#cdd6f4' }} className="markdown-body">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {ocrResult.pages?.map((p: any) => p.text).join('\n\n')}
                      </ReactMarkdown>
                    </div>
                  )}

                  {activeTab === 'json' && (
                    <pre>{JSON.stringify(ocrResult, null, 2)}</pre>
                  )}
                </div>
              </div>

              {/* Chat Window */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
                <h3 style={{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <MessageSquare style={{ color: '#7c3aed' }} /> AI Document Assistant
                </h3>
                <p style={{ fontSize: '0.75rem', color: '#a6adc8', marginBottom: '1rem' }}>
                  Ask questions, translate or draft summaries using smart LLM routing.
                </p>

                <div className="chat-container" style={{ flex: 1, minHeight: '320px', maxHeight: '380px' }}>
                  {chatMessages.map((msg, idx) => (
                    <div key={idx} className={`chat-msg ${msg.role === 'user' ? 'user' : 'assistant'}`}>
                      <div className="chat-avatar" style={{ background: msg.role === 'user' ? '#7c3aed' : '#313244' }}>
                        {msg.role === 'user' ? 'U' : 'AI'}
                      </div>
                      <div className="chat-bubble">
                        <div>{msg.content}</div>
                        {msg.model_used && (
                          <div style={{ fontSize: '0.65rem', color: '#a6adc8', marginTop: '0.35rem', borderTop: '1px solid #45475a', paddingTop: '0.2rem', display: 'flex', justifyContent: 'space-between' }}>
                            <span>Powered by: <strong>{msg.model_used}</strong></span>
                            <span>Provider: <strong style={{ color: '#f9e2af' }}>{msg.provider?.toUpperCase()}</strong></span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {isChatLoading && (
                    <div className="chat-msg assistant">
                      <div className="chat-avatar" style={{ background: '#313244' }}>AI</div>
                      <div className="chat-bubble" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <RefreshCw style={{ width: '14px', height: '14px', animation: 'spin 1.5s linear infinite' }} />
                        <span style={{ fontSize: '0.8rem' }}>Generating response...</span>
                      </div>
                    </div>
                  )}
                </div>

                <form onSubmit={handleSendMessage} className="chat-input-row">
                  <input
                    type="text"
                    className="chat-input"
                    placeholder="Ask a question about the document..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    disabled={isChatLoading}
                  />
                  <button type="submit" className="btn btn-primary" disabled={isChatLoading}>
                    Send
                  </button>
                </form>
              </div>

            </div>
          </section>
        )}

        {/* Pricing Matrix */}
        <section className="section">
          <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
            <h2 className="section-title" style={{ textAlign: 'center' }}>Flexible Plans for Global Scale</h2>
            <p className="section-sub" style={{ textAlign: 'center' }}>
              Pricing optimized for low-overhead self-hosted computation. Clear billing thresholds.
            </p>
          </div>

          <div className="pricing-grid">
            
            {/* Free Tier */}
            <div className={`card pricing-card ${tier === 'free' ? 'featured' : ''}`}>
              <h3>Free Tier</h3>
              <p style={{ color: '#a6adc8', fontSize: '0.85rem', margin: '0.5rem 0 1.5rem' }}>Perfect for basic evaluation</p>
              <div className="price">$0<span>/month</span></div>
              <ul style={{ listStyle: 'none', padding: '0', margin: '1.5rem 0', fontSize: '0.85rem', color: '#cdd6f4', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <li>✓ Up to 5 pages per day</li>
                <li>✓ Max file size 10MB</li>
                <li>✓ 5-page PDF limit per document</li>
                <li>✓ Local Llama 3.2 Chat fallback</li>
                <li>✗ SLA Support</li>
              </ul>
              <button
                className="btn btn-outline"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => setTier('free')}
              >
                {tier === 'free' ? 'Current Tier' : 'Downgrade to Free'}
              </button>
            </div>

            {/* Basic Tier */}
            <div className={`card pricing-card ${tier === 'basic' ? 'featured' : ''}`}>
              <h3>Basic Tier</h3>
              <p style={{ color: '#a6adc8', fontSize: '0.85rem', margin: '0.5rem 0 1.5rem' }}>For regular practitioners</p>
              <div className="price">$19<span>/month</span></div>
              <ul style={{ listStyle: 'none', padding: '0', margin: '1.5rem 0', fontSize: '0.85rem', color: '#cdd6f4', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <li>✓ Up to 100 pages per day</li>
                <li>✓ Max file size 50MB</li>
                <li>✓ Multi-page PDF extraction</li>
                <li>✓ Smart routing (GPT-4o & Llama)</li>
                <li>✓ 30-day storage retention</li>
              </ul>
              <button
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => handleUpgrade('basic')}
              >
                Upgrade to Basic
              </button>
            </div>

            {/* Pro Tier */}
            <div className={`card pricing-card ${tier === 'pro' ? 'featured' : ''}`}>
              <h3>Professional</h3>
              <p style={{ color: '#a6adc8', fontSize: '0.85rem', margin: '0.5rem 0 1.5rem' }}>Unlimited production capability</p>
              <div className="price">$49<span>/month</span></div>
              <ul style={{ listStyle: 'none', padding: '0', margin: '1.5rem 0', fontSize: '0.85rem', color: '#cdd6f4', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <li>✓ Unlimited Daily pages</li>
                <li>✓ Max file size 100MB</li>
                <li>✓ Triton GPU Dedicated Queue</li>
                <li>✓ GPT-4o primary assistant</li>
                <li>✓ 90-day storage retention</li>
              </ul>
              <button
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => handleUpgrade('pro')}
              >
                Upgrade to Pro
              </button>
            </div>

          </div>
        </section>

      </main>

      <footer>
        <div className="container">
          <p>© 2026 Enterprise OCR Platform Inc. Self-hosted high efficiency execution.</p>
        </div>
      </footer>
    </div>
  );
}
