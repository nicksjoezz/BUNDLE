import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Terminal,
  Wallet,
  Rocket,
  Settings,
  TrendingUp,
  Cpu,
  Shield,
  Database,
  RefreshCw,
  Send,
  Zap,
  DollarSign,
  Fingerprint,
  Flame,
  Coffee
} from 'lucide-react';
import axios from 'axios';

const API_BASE = '/api';

const App = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState({ tokens: [], performance: { total_profit: 0, launches: 0 } });
  const [wallets, setWallets] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [logs, setLogs] = useState(["[SYSTEM] Initializing hacking module...", "[SYSTEM] Connection established."]);

  const addLog = (msg) => {
    setLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev.slice(0, 49)]);
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statusRes, historyRes, walletRes, tasksRes] = await Promise.all([
          axios.get(`${API_BASE}/status`),
          axios.get(`${API_BASE}/history`),
          axios.get(`${API_BASE}/wallets`),
          axios.get(`${API_BASE}/tasks`)
        ]);
        setStatus(statusRes.data);
        setHistory(historyRes.data);
        setWallets(walletRes.data);
        setTasks(tasksRes.data);
      } catch (err) {
        addLog(`[ERROR] Failed to fetch data: ${err.message}`);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const renderTab = () => {
    switch(activeTab) {
      case 'dashboard': return <Dashboard history={history} status={status} tasks={tasks} />;
      case 'history': return <TokenHistory history={history} />;
      case 'operations': return <Operations status={status} addLog={addLog} />;
      case 'wallets': return <Wallets wallets={wallets} addLog={addLog} />;
      case 'launch': return <Launch addLog={addLog} maxWallets={status?.sub_wallets_count || 0} />;
      case 'sell': return <Sell wallets={wallets} addLog={addLog} />;
      case 'settings': return <Config addLog={addLog} />;
      default: return null;
    }
  };

  return (
    <div className="min-h-screen p-2 md:p-4 flex flex-col gap-4 max-w-7xl mx-auto relative overflow-hidden">
      <div className="scanline" />
      {/* Matrix Background Effect */}
      <div className="fixed inset-0 pointer-events-none opacity-5 z-[-1] overflow-hidden">
        <motion.div
          animate={{ y: [0, -1000] }}
          transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
          className="text-[10px] leading-tight break-all"
        >
          {Array(100).fill(0).map((_, i) => (
            <div key={i}>{Math.random().toString(36).substring(2, 15).repeat(20)}</div>
          ))}
        </motion.div>
      </div>

      {/* Header */}
      <header className="hacker-border p-3 md:p-4 hacker-bg flex flex-col sm:flex-row justify-between items-center gap-4">
        <div className="flex items-center gap-3">
          <Terminal className="text-hacker-green w-6 h-6 md:w-8 md:h-8 animate-pulse" />
          <h1 className="text-lg md:text-2xl font-bold tracking-tighter glitch" data-text="INFINITYATO_OS v2.0">
            INFINITY<span className="text-white">ATO</span>_OS v2.0
          </h1>
        </div>
        <div className="flex gap-4 text-[10px] md:text-xs">
          <div className="flex flex-col items-end">
            <span className="text-hacker-muted uppercase tracking-widest">Network</span>
            <span className="text-hacker-green font-bold">SOLANA MAINNET</span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-hacker-muted uppercase tracking-widest">Status</span>
            <span className={status?.initialized ? "text-hacker-green" : "text-red-500"}>
              {status?.initialized ? "● ONLINE" : "● OFFLINE"}
            </span>
          </div>
        </div>
      </header>

      <div className="flex flex-col md:grid md:grid-cols-4 gap-4 flex-grow">
        {/* Sidebar / Mobile Nav */}
        <nav className="hacker-border p-2 md:p-4 hacker-bg flex md:flex-col gap-1 md:gap-2 overflow-x-auto md:overflow-x-visible no-scrollbar">
          <NavButton active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} icon={<TrendingUp />} label="DB" fullLabel="DASHBOARD" />
          <NavButton active={activeTab === 'history'} onClick={() => setActiveTab('history')} icon={<Database />} label="HT" fullLabel="HISTORY" />
          <NavButton active={activeTab === 'operations'} onClick={() => setActiveTab('operations')} icon={<Zap />} label="OP" fullLabel="OPERATIONS" />
          <NavButton active={activeTab === 'wallets'} onClick={() => setActiveTab('wallets')} icon={<Wallet />} label="WL" fullLabel="WALLETS" />
          <NavButton active={activeTab === 'launch'} onClick={() => setActiveTab('launch')} icon={<Rocket />} label="LN" fullLabel="LAUNCH" />
          <NavButton active={activeTab === 'sell'} onClick={() => setActiveTab('sell')} icon={<DollarSign />} label="SL" fullLabel="SELL" />
          <NavButton active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} icon={<Settings />} label="ST" fullLabel="SETTINGS" />

          <div className="mt-auto pt-4 border-t border-hacker-muted hidden md:block">
             <div className="text-[10px] text-hacker-muted mb-2">SYSTEM LOAD</div>
             <div className="w-full bg-hacker-muted h-1">
               <motion.div
                 className="bg-hacker-green h-full"
                 animate={{ width: ["10%", "85%", "40%"] }}
                 transition={{ duration: 5, repeat: Infinity }}
               />
             </div>
          </div>
        </nav>

        {/* Main Content */}
        <main className="md:col-span-3 flex flex-col gap-4">
          <div className="hacker-border p-6 hacker-bg flex-grow relative overflow-hidden min-h-[500px]">
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                {renderTab()}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Console */}
          <div className="hacker-border h-40 hacker-bg p-2 text-xs font-mono overflow-y-auto flex flex-col-reverse">
            {logs.map((log, i) => (
              <div key={i} className={log.includes('ERROR') ? 'text-red-500' : 'text-hacker-green opacity-80'}>
                {log}
              </div>
            ))}
            <div className="text-hacker-muted underline mb-1">TERMINAL_OUTPUT</div>
          </div>
        </main>
      </div>
    </div>
  );
};

const NavButton = ({ active, onClick, icon, label, fullLabel }) => (
  <button
    onClick={onClick}
    className={`flex items-center justify-center md:justify-start gap-3 p-2 md:p-3 transition-all border md:border-none ${
      active
        ? 'bg-hacker-green text-black border-hacker-green'
        : 'hover:bg-hacker-muted text-hacker-green border-transparent'
    }`}
  >
    {React.cloneElement(icon, { size: 18 })}
    <span className="font-bold text-[10px] md:text-sm tracking-widest hidden sm:inline md:hidden lg:inline">{fullLabel}</span>
    <span className="font-bold text-[10px] sm:hidden">{label}</span>
  </button>
);

const Operations = ({ status, addLog }) => {
  const [volumeData, setVolumeData] = useState({ mint_address: '', duration: 60, min_buy: 0.01, max_buy: 0.1 });

  const startVolume = async () => {
    try {
      addLog(`Starting volume bot for ${volumeData.mint_address}...`);
      await axios.post(`${API_BASE}/volume/start`, volumeData);
      addLog("Volume protocol initiated.");
    } catch (e) { addLog(`[ERROR] Volume start failed: ${e.message}`); }
  };

  const stopVolume = async (mint) => {
    try {
      await axios.post(`${API_BASE}/volume/stop`, { mint_address: mint });
      addLog(`Stopped volume bot for ${mint}`);
    } catch (e) { addLog(`[ERROR] Volume stop failed: ${e.message}`); }
  };

  return (
    <div className="flex flex-col gap-6">
       <h2 className="text-xl font-bold flex items-center gap-2"><Zap size={20} /> OPERATIONS_CENTER</h2>
       <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="hacker-border p-4 hacker-bg">
             <h3 className="text-sm font-bold mb-4 text-hacker-green">MARKET_MAKER_VOLUME_BOT</h3>
             <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-1">
                   <label className="text-[10px] text-hacker-muted uppercase">TOKEN_MINT_ADDRESS</label>
                   <input className="input-hacker text-xs" value={volumeData.mint_address} onChange={e => setVolumeData({...volumeData, mint_address: e.target.value})} placeholder="Pubkey..." />
                </div>
                <div className="grid grid-cols-2 gap-3">
                   <div className="flex flex-col gap-1">
                      <label className="text-[10px] text-hacker-muted uppercase">DURATION_MINS</label>
                      <input type="number" className="input-hacker text-xs" value={volumeData.duration} onChange={e => setVolumeData({...volumeData, duration: parseInt(e.target.value)})} />
                   </div>
                   <div className="flex flex-col gap-1">
                      <label className="text-[10px] text-hacker-muted uppercase">DELAY</label>
                      <div className="text-[10px] py-2 opacity-50 italic">Dynamic (2-10s)</div>
                   </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                   <div className="flex flex-col gap-1">
                      <label className="text-[10px] text-hacker-muted uppercase">MIN_BUY_SOL</label>
                      <input type="number" step="0.01" className="input-hacker text-xs" value={volumeData.min_buy} onChange={e => setVolumeData({...volumeData, min_buy: parseFloat(e.target.value)})} />
                   </div>
                   <div className="flex flex-col gap-1">
                      <label className="text-[10px] text-hacker-muted uppercase">MAX_BUY_SOL</label>
                      <input type="number" step="0.01" className="input-hacker text-xs" value={volumeData.max_buy} onChange={e => setVolumeData({...volumeData, max_buy: parseFloat(e.target.value)})} />
                   </div>
                </div>
                <button onClick={startVolume} className="btn-hacker mt-2 bg-hacker-green text-black font-bold">START_VOLUME_BOT</button>
             </div>
          </div>

          <div className="hacker-border p-4 hacker-bg border-hacker-muted">
             <h3 className="text-sm font-bold mb-4">ACTIVE_VOLUME_NODES</h3>
             <div className="space-y-2">
                {status?.volume_bots_active?.length === 0 ? (
                  <div className="text-xs text-hacker-muted italic">No active volume bots detected.</div>
                ) : (
                  status?.volume_bots_active?.map((mint, i) => (
                    <div key={i} className="flex justify-between items-center bg-hacker-muted bg-opacity-20 p-2 border-l-2 border-hacker-green">
                       <span className="text-[10px] font-mono break-all max-w-[150px]">{mint}</span>
                       <button onClick={() => stopVolume(mint)} className="text-red-500 text-[10px] border border-red-500 px-2 py-1 hover:bg-red-500 hover:text-white transition-colors">STOP</button>
                    </div>
                  ))
                )}
             </div>
          </div>
       </div>
    </div>
  );
};

const TokenHistory = ({ history }) => (
  <div className="flex flex-col gap-4">
    <h2 className="text-xl font-bold flex items-center gap-2"><Database size={20} /> TOKEN_REGISTRY</h2>
    <div className="hacker-border hacker-bg overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="border-b border-hacker-muted bg-hacker-muted bg-opacity-30">
          <tr>
            <th className="p-3">NAME</th>
            <th className="p-3">SYMBOL</th>
            <th className="p-3">ADDRESS</th>
            <th className="p-3">TYPE</th>
            <th className="p-3 text-right">TIMESTAMP</th>
          </tr>
        </thead>
        <tbody>
          {history.tokens.length === 0 ? (
            <tr><td colSpan="5" className="p-8 text-center text-hacker-muted italic">No tokens found in database.</td></tr>
          ) : (
            history.tokens.map((t, i) => (
              <tr key={i} className="border-b border-hacker-muted hover:bg-hacker-muted hover:bg-opacity-10">
                <td className="p-3">{t.name}</td>
                <td className="p-3">{t.symbol}</td>
                <td className="p-3 font-mono opacity-70 break-all">{t.address}</td>
                <td className="p-3 capitalize">{t.type}</td>
                <td className="p-3 text-right opacity-50">{new Date(t.timestamp * 1000).toLocaleString()}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  </div>
);

const Dashboard = ({ history, status, tasks }) => (
  <div className="flex flex-col gap-6">
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Capability Overview */}
      <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
         <CapabilityCard
           title="ATOMIC BUNDLING"
           desc="Atomic Jito-bundles for 20+ wallet buys in the same block."
           icon={<Zap className="text-hacker-green" />}
         />
         <CapabilityCard
           title="VOLUME GENERATION"
           desc="Market Maker bots to generate organic-looking chart volume."
           icon={<TrendingUp className="text-hacker-green" />}
         />
         <CapabilityCard
           title="SNIPER FARMING"
           desc="Automated multi-token monitoring and liquidity-based exits."
           icon={<Shield className="text-hacker-green" />}
         />
         <CapabilityCard
           title="STEALTH EXITS"
           desc="Aggregate and liquidate via clean targets to hide dev footprints."
           icon={<DollarSign className="text-hacker-green" />}
         />
      </div>

      {/* Stats */}
      <div className="p-4 border border-hacker-muted relative overflow-hidden group hacker-bg">
        <h3 className="text-hacker-muted mb-4 flex items-center gap-2">
          <Cpu size={14} /> CORE_METRICS
        </h3>
        <div className="grid grid-cols-1 gap-4">
          <MetricCard label="CUMULATIVE LAUNCHES" value={history.performance.launches} />
          <MetricCard label="MANAGED FLEET" value={`${status?.sub_wallets_count || 0} WALLETS`} />
          <MetricCard label="NET REALIZED PROFIT" value={`${history.performance.total_profit} SOL`} />
          <MetricCard label="NODES RUNNING" value={tasks.filter(t => t.status === "running").length} />
        </div>
      </div>
    </div>

    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="p-4 border border-hacker-muted">
        <h3 className="text-hacker-muted mb-4 flex items-center gap-2">
          <Database size={14} /> RECENT LAUNCHES
        </h3>
        <div className="space-y-2 max-h-40 overflow-y-auto">
          {history.tokens.length === 0 ? (
            <div className="text-hacker-muted text-sm italic">No tokens launched yet...</div>
          ) : (
            history.tokens.map((t, i) => (
              <div key={i} className="flex justify-between text-xs p-2 bg-hacker-muted bg-opacity-20 border-l-2 border-hacker-green">
                <span>{t.name} ({t.symbol})</span>
                <span className="opacity-50">{new Date(t.timestamp * 1000).toLocaleDateString()}</span>
              </div>
            ))
          )}
        </div>
      </div>
      <div className="p-4 border border-hacker-muted relative">
         <h3 className="text-hacker-muted mb-4 flex items-center gap-2">
          <RefreshCw size={14} /> ACTIVE_TASK_MONITOR
        </h3>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {tasks.length === 0 ? (
            <div className="text-hacker-muted text-sm italic">No active tasks being monitored.</div>
          ) : (
            tasks.slice().reverse().map((t, i) => (
              <div key={i} className="flex justify-between items-center text-xs p-3 bg-hacker-muted bg-opacity-10 border border-hacker-muted border-l-4 border-l-hacker-green">
                <div className="flex items-center gap-4">
                  <span className="font-bold uppercase text-hacker-green tracking-tighter">{t.type}</span>
                  <span className="opacity-80">{t.name}</span>
                </div>
                <div className="flex items-center gap-4">
                   <span className={`px-2 py-0.5 rounded-full text-[8px] font-bold ${
                     t.status === 'running' ? 'bg-blue-900 text-blue-200 animate-pulse' :
                     t.status === 'success' ? 'bg-green-900 text-green-200' :
                     'bg-red-900 text-red-200'
                   }`}>
                     {t.status.toUpperCase()}
                   </span>
                   <span className="text-hacker-muted opacity-50">{new Date(t.timestamp * 1000).toLocaleTimeString()}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  </div>
);

const CapabilityCard = ({ title, desc, icon }) => (
  <div className="hacker-border p-4 hacker-bg border-hacker-muted hover:border-hacker-green transition-colors group">
    <div className="flex items-center gap-3 mb-2">
      {icon}
      <h4 className="text-xs font-bold tracking-widest">{title}</h4>
    </div>
    <p className="text-[10px] text-hacker-muted leading-relaxed">{desc}</p>
  </div>
);

const MetricCard = ({ label, value }) => (
  <div className="bg-hacker-muted bg-opacity-10 p-3 border border-hacker-muted">
    <div className="text-[10px] text-hacker-muted mb-1">{label}</div>
    <div className="text-xl font-bold">{value}</div>
  </div>
);

const Wallets = ({ wallets, addLog }) => {
  const [transferData, setTransferData] = useState(null); // { from_index, address }
  const [vanityStatus, setVanityStatus] = useState({ is_running: false, found_count: 0, current_match: "" });
  const [vanityMatch, setVanityMatch] = useState("");
  const [vanityPos, setVanityPos] = useState("front");

  useEffect(() => {
    const fetchVanity = async () => {
      try {
        const res = await axios.get(`${API_BASE}/wallets/vanity/status`);
        setVanityStatus(res.data);
      } catch (e) {}
    };
    const interval = setInterval(fetchVanity, 2000);
    return () => clearInterval(interval);
  }, []);

  const startVanity = async () => {
    try {
      await axios.post(`${API_BASE}/wallets/vanity/start`, {
        match_str: vanityMatch,
        position: vanityPos,
        threads: 4
      });
      addLog(`Started vanity generation for '${vanityMatch}'`);
    } catch (e) { addLog(`[ERROR] Vanity start failed: ${e.message}`); }
  };

  const stopVanity = async () => {
    try {
      await axios.post(`${API_BASE}/wallets/vanity/stop`);
      addLog("Vanity generation stopped.");
    } catch (e) { addLog(`[ERROR] Vanity stop failed: ${e.message}`); }
  };

  const warmup = async () => {
    try {
      addLog("Starting wallet warmup protocol...");
      await axios.post(`${API_BASE}/wallets/warmup`);
      addLog("Warmup initiated.");
    } catch (e) { addLog(`[ERROR] Warmup failed: ${e.message}`); }
  };

  const burnDev = async () => {
    const addr = prompt("Enter token address to burn from dev wallet:");
    if (!addr) return;
    try {
      addLog(`Burning supply for ${addr}...`);
      await axios.post(`${API_BASE}/wallets/burn-dev-supply`, { address: addr });
      addLog("Burn successful.");
    } catch (e) { addLog(`[ERROR] Burn failed: ${e.message}`); }
  };

  const refreshBalances = async () => {
    try {
      await axios.post(`${API_BASE}/wallets/balances`);
      addLog("Balances updated successfully.");
    } catch (err) {
      addLog(`[ERROR] Refresh failed: ${err.message}`);
    }
  };

  const reclaim = async () => {
    try {
      await axios.post(`${API_BASE}/wallets/reclaim`);
      addLog("Reclaim process started.");
    } catch (err) {
      addLog(`[ERROR] Reclaim failed: ${err.message}`);
    }
  };

  const fundAll = async () => {
    const amount = prompt("Enter amount (SOL) to fund each sub-wallet:", "0.01");
    if (!amount) return;
    try {
      addLog(`Funding sub-wallets with ${amount} SOL each...`);
      const subWallets = wallets.filter(w => w.type === 'sub');
      await axios.post(`${API_BASE}/wallets/fund`, {
        amounts: Array(subWallets.length).fill(parseFloat(amount))
      });
      addLog("Funding initiated.");
    } catch (err) {
      addLog(`[ERROR] Funding failed: ${err.message}`);
    }
  };

  const generateWallets = async () => {
    const num = prompt("How many sub-wallets would you like to generate?", "20");
    if (!num) return;
    try {
      addLog(`Generating ${num} sub-wallets and saving to output...`);
      await axios.post(`${API_BASE}/wallets/generate`, { num: parseInt(num) });
      addLog("Generation complete.");
    } catch (err) {
      addLog(`[ERROR] Generation failed: ${err.message}`);
    }
  };

  const exportWallets = async () => {
    try {
      const res = await axios.get(`${API_BASE}/wallets/export`);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'wallets.json';
      a.click();
      addLog("Wallet registry exported.");
    } catch (err) {
      addLog(`[ERROR] Export failed: ${err.message}`);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap justify-between items-center gap-2">
        <h2 className="text-xl font-bold flex items-center gap-2"><Shield size={20} /> WALLET_ARRAY</h2>
        <div className="flex gap-2">
          <button onClick={refreshBalances} className="btn-hacker text-xs flex items-center gap-1">
            <RefreshCw size={12} /> REFRESH
          </button>
          <button onClick={generateWallets} className="btn-hacker text-xs border-green-500 text-green-500 hover:bg-green-500 hover:text-white">
            GENERATE
          </button>
          <button onClick={exportWallets} className="btn-hacker text-xs border-cyan-500 text-cyan-500 hover:bg-cyan-500 hover:text-white">
            EXPORT
          </button>
          <button onClick={warmup} className="btn-hacker text-xs border-orange-500 text-orange-500 hover:bg-orange-500 hover:text-white flex items-center gap-1">
            <Coffee size={12} /> WARMUP
          </button>
          <button onClick={burnDev} className="btn-hacker text-xs border-purple-500 text-purple-500 hover:bg-purple-500 hover:text-white flex items-center gap-1">
            <Flame size={12} /> BURN DEV
          </button>
          <button onClick={fundAll} className="btn-hacker text-xs border-blue-500 text-blue-500 hover:bg-blue-500 hover:text-white">
            FUND ALL
          </button>
          <button onClick={reclaim} className="btn-hacker text-xs border-red-500 text-red-500 hover:bg-red-500 hover:text-white">
            RECLAIM ALL
          </button>
        </div>
      </div>

      {/* Vanity Generator Section */}
      <div className="hacker-border p-4 hacker-bg border-hacker-green bg-opacity-10 mb-2">
        <h3 className="text-xs font-bold mb-3 flex items-center gap-2"><Fingerprint size={14} /> VANITY_ADDRESS_ENGINE</h3>
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-hacker-muted">MATCH_STRING</label>
            <input
              className="input-hacker text-xs w-32"
              placeholder="e.g. ace"
              value={vanityMatch}
              onChange={e => setVanityMatch(e.target.value)}
              disabled={vanityStatus.is_running}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] text-hacker-muted">POSITION</label>
            <select
              className="input-hacker text-xs bg-black"
              value={vanityPos}
              onChange={e => setVanityPos(e.target.value)}
              disabled={vanityStatus.is_running}
            >
              <option value="front">FRONT</option>
              <option value="back">BACK</option>
            </select>
          </div>
          <div className="flex gap-2">
            {!vanityStatus.is_running ? (
              <button onClick={startVanity} className="btn-hacker text-[10px] bg-hacker-green text-black px-4">START_MINING</button>
            ) : (
              <button onClick={stopVanity} className="btn-hacker text-[10px] border-red-500 text-red-500 px-4">STOP_MINING</button>
            )}
          </div>
          {vanityStatus.is_running && (
            <div className="flex flex-col ml-auto text-right">
              <span className="text-[10px] text-hacker-muted">FOUND_WALLETS</span>
              <span className="text-sm font-bold animate-pulse text-hacker-green">{vanityStatus.found_count}</span>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2 max-h-[300px] overflow-y-auto pr-2">
        {wallets.map((w, i) => (
          <div key={i} className="hacker-border p-3 hacker-bg flex justify-between items-center group">
            <div className="flex flex-col">
              <span className="text-[10px] text-hacker-muted">{w.type.toUpperCase()} WALLET {w.type === 'main' ? '' : (w.index || i)}</span>
              <span className="text-xs opacity-70 group-hover:opacity-100 transition-opacity break-all max-w-[150px] sm:max-w-none">{w.address}</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-sm font-bold">{w.balance.toFixed(4)} SOL</div>
                {w.token_balances && Object.keys(w.token_balances).length > 0 && (
                   <div className="text-[10px] text-hacker-muted">{Object.keys(w.token_balances).length} TOKENS</div>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <button
                  onClick={() => setTransferData({ from_index: w.type === 'main' ? 0 : (w.index || i), address: w.address })}
                  className="opacity-0 group-hover:opacity-100 btn-hacker p-1 text-[8px] uppercase"
                >
                  TX SOL
                </button>
                <button
                  onClick={async () => {
                    const perc = prompt("Percentage to sell (1-100):", "100");
                    if (!perc) return;
                    try {
                      await axios.post(`${API_BASE}/sell/single`, { address: w.address, percentage: parseFloat(perc) });
                      addLog(`Single sell initiated for ${w.address}`);
                    } catch (e) { addLog(`[ERROR] Sell failed: ${e.message}`); }
                  }}
                  className="opacity-0 group-hover:opacity-100 btn-hacker p-1 text-[8px] uppercase border-red-500 text-red-500"
                >
                  SELL
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <AnimatePresence>
        {transferData && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center p-4 z-50"
          >
            <div className="hacker-border p-6 hacker-bg max-w-sm w-full flex flex-col gap-4">
              <h3 className="text-lg font-bold">TRANSFER_SOL</h3>
              <div className="text-xs text-hacker-muted uppercase">From: {transferData.address}</div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-hacker-muted">RECIPIENT_ADDRESS</label>
                <input id="tx-to" className="input-hacker text-xs" placeholder="Pubkey..." />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-hacker-muted">AMOUNT_SOL</label>
                <input id="tx-amount" type="number" step="0.01" className="input-hacker text-xs" placeholder="0.1" />
              </div>
              <div className="flex gap-2 mt-2">
                <button
                  className="btn-hacker flex-grow"
                  onClick={async () => {
                    const to = document.getElementById('tx-to').value;
                    const amt = document.getElementById('tx-amount').value;
                    try {
                      await axios.post(`${API_BASE}/wallets/transfer-sol`, {
                        from_index: transferData.from_index,
                        to_address: to,
                        amount: amt
                      });
                      addLog(`Transferred ${amt} SOL to ${to}`);
                      setTransferData(null);
                    } catch (e) { addLog(`[ERROR] Transfer failed: ${e.message}`); }
                  }}
                >
                  EXECUTE_TRANSFER
                </button>
                <button className="btn-hacker border-red-500 text-red-500" onClick={() => setTransferData(null)}>CANCEL</button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const Launch = ({ addLog, maxWallets }) => {
  const [mode, setMode] = useState('bundle'); // 'bundle' or 'sniper-farmer'
  const [formData, setFormData] = useState({
    name: '', symbol: '', description: '', wallets: Math.min(3, maxWallets), amount: 0.01, devBuy: 0.001,
    telegram: '', twitter: '', website: ''
  });

  // Sniper Farmer State
  const [sniperTokens, setSniperTokens] = useState([{ name: '', symbol: '', description: '', threshold: 100, devBuy: 0.001 }]);

  const [image, setImage] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      addLog(`Initiating bundle launch for ${formData.name}...`);

      const data = new FormData();
      data.append('name', formData.name);
      data.append('symbol', formData.symbol);
      data.append('description', formData.description);
      data.append('telegram', formData.telegram);
      data.append('twitter', formData.twitter);
      data.append('website', formData.website);
      data.append('num_wallets', formData.wallets);
      data.append('amount', formData.amount);
      data.append('dev_buy_amount', formData.devBuy);
      if (image) data.append('image', image);

      await axios.post(`${API_BASE}/launch/bundle`, data, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      addLog(`Launch request sent for ${formData.symbol}`);
    } catch (err) {
      addLog(`[ERROR] Launch failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSniperSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      addLog(`Initiating sniper-farmer for ${sniperTokens.length} tokens...`);
      await axios.post(`${API_BASE}/launch/sniper-farmer`, {
        tokens: sniperTokens,
        liquidity_threshold_usds: sniperTokens.map(t => t.threshold),
        dev_buy_amounts: sniperTokens.map(t => t.devBuy),
        use_jito: true
      });
      addLog("Sniper farmer protocol engaged.");
    } catch (err) {
      addLog(`[ERROR] Sniper farmer failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto">
      <div className="flex flex-wrap justify-between items-center gap-4 mb-6">
        <h2 className="text-xl font-bold flex items-center gap-2"><Zap size={20} /> TOKEN_FORGE</h2>
        <div className="flex flex-wrap bg-hacker-muted bg-opacity-20 p-1 rounded gap-1">
           {['bundle', 'clone-snipe', 'snipe-only', 'bundle-stagger', 'sniper-farmer'].map(m => (
             <button
               key={m}
               onClick={() => setMode(m)}
               className={`px-2 py-1 text-[9px] font-bold transition-all uppercase ${mode === m ? 'bg-hacker-green text-black' : 'text-hacker-muted hover:text-white'}`}
             >
               {m.replace('-', '_')}
             </button>
           ))}
        </div>
      </div>

      {mode === 'bundle' || mode === 'bundle-stagger' ? (
      <form onSubmit={async (e) => {
          e.preventDefault();
          setLoading(true);
          try {
            const data = new FormData();
            data.append('name', formData.name);
            data.append('symbol', formData.symbol);
            data.append('description', formData.description);
            data.append('telegram', formData.telegram);
            data.append('twitter', formData.twitter);
            data.append('website', formData.website);
            data.append('num_wallets', formData.wallets);
            data.append('amount', formData.amount);
            data.append('dev_buy_amount', formData.devBuy);
            if (image) data.append('image', image);

            if (mode === 'bundle-stagger') {
              data.append('delay', prompt("Enter stagger delay (sec):", "1.0"));
              await axios.post(`${API_BASE}/launch/bundle-stagger`, data);
            } else {
              await axios.post(`${API_BASE}/launch/bundle`, data);
            }
            addLog(`Initiated ${mode} for ${formData.symbol}`);
          } catch (err) { addLog(`[ERROR] ${mode} failed: ${err.message}`); }
          finally { setLoading(false); }
      }} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-hacker-muted">NAME</label>
            <input className="input-hacker" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-hacker-muted">SYMBOL</label>
            <input className="input-hacker" value={formData.symbol} onChange={e => setFormData({...formData, symbol: e.target.value})} />
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-hacker-muted">DESCRIPTION</label>
          <textarea className="input-hacker h-16" value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-hacker-muted">TELEGRAM</label>
            <input className="input-hacker text-xs" value={formData.telegram} onChange={e => setFormData({...formData, telegram: e.target.value})} placeholder="https://t.me/..." />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-hacker-muted">TWITTER</label>
            <input className="input-hacker text-xs" value={formData.twitter} onChange={e => setFormData({...formData, twitter: e.target.value})} placeholder="https://x.com/..." />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-hacker-muted">WEBSITE</label>
            <input className="input-hacker text-xs" value={formData.website} onChange={e => setFormData({...formData, website: e.target.value})} placeholder="https://..." />
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-hacker-muted">TOKEN IMAGE</label>
          <input type="file" className="input-hacker text-xs" onChange={e => setImage(e.target.files[0])} accept="image/*" />
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-hacker-muted">WALLETS (MAX {maxWallets})</label>
            <input
              type="number"
              max={maxWallets}
              min="1"
              className="input-hacker"
              value={formData.wallets}
              onChange={e => setFormData({...formData, wallets: Math.min(e.target.value, maxWallets)})}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-hacker-muted">BUY AMT</label>
            <input type="number" step="0.01" className="input-hacker" value={formData.amount} onChange={e => setFormData({...formData, amount: e.target.value})} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-hacker-muted">DEV BUY</label>
            <input type="number" step="0.001" className="input-hacker" value={formData.devBuy} onChange={e => setFormData({...formData, devBuy: e.target.value})} />
          </div>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="btn-hacker mt-4 font-bold tracking-widest flex justify-center items-center gap-2"
        >
          {loading ? <RefreshCw className="animate-spin" size={18} /> : <Rocket size={18} />}
          {loading ? 'INITIALIZING...' : `INITIALIZE ${mode.toUpperCase().replace('-', ' ')}`}
        </button>
      </form>
      ) : mode === 'clone-snipe' ? (
        <form onSubmit={async (e) => {
          e.preventDefault();
          setLoading(true);
          try {
            const target = prompt("Enter existing token address to clone:");
            if (!target) return;
            await axios.post(`${API_BASE}/launch/clone-snipe`, {
              token: { name: formData.name, symbol: formData.symbol },
              num_wallets: formData.wallets,
              amounts: Array(parseInt(formData.wallets)).fill(parseFloat(formData.amount)),
              existing_address: target,
              dev_buy_amount: formData.devBuy
            });
            addLog(`Initiated clone+snipe from ${target}`);
          } catch (err) { addLog(`[ERROR] Clone+Snipe failed: ${err.message}`); }
          finally { setLoading(false); }
        }} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-hacker-muted">DUMMY NAME</label>
              <input className="input-hacker" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-hacker-muted">DUMMY SYMBOL</label>
              <input className="input-hacker" value={formData.symbol} onChange={e => setFormData({...formData, symbol: e.target.value})} />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-hacker-muted">WALLETS</label>
              <input type="number" className="input-hacker" value={formData.wallets} onChange={e => setFormData({...formData, wallets: e.target.value})} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-hacker-muted">BUY AMT</label>
              <input type="number" step="0.01" className="input-hacker" value={formData.amount} onChange={e => setFormData({...formData, amount: e.target.value})} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-hacker-muted">DEV BUY</label>
              <input type="number" step="0.001" className="input-hacker" value={formData.devBuy} onChange={e => setFormData({...formData, devBuy: e.target.value})} />
            </div>
          </div>
          <button type="submit" disabled={loading} className="btn-hacker mt-4 font-bold tracking-widest uppercase">
             {loading ? 'CLONING...' : 'INITIALIZE CLONE + SNIPE'}
          </button>
        </form>
      ) : mode === 'snipe-only' ? (
        <form onSubmit={async (e) => {
          e.preventDefault();
          setLoading(true);
          try {
            const addr = prompt("Enter token address to snipe:");
            if (!addr) return;
            await axios.post(`${API_BASE}/launch/snipe-only`, {
              mint_address: addr,
              num_wallets: formData.wallets,
              amounts: Array(parseInt(formData.wallets)).fill(parseFloat(formData.amount))
            });
            addLog(`Snipe protocol engaged for ${addr}`);
          } catch (err) { addLog(`[ERROR] Snipe failed: ${err.message}`); }
          finally { setLoading(false); }
        }} className="flex flex-col gap-4">
           <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-hacker-muted">WALLETS</label>
              <input type="number" className="input-hacker" value={formData.wallets} onChange={e => setFormData({...formData, wallets: e.target.value})} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-hacker-muted">BUY AMT</label>
              <input type="number" step="0.01" className="input-hacker" value={formData.amount} onChange={e => setFormData({...formData, amount: e.target.value})} />
            </div>
          </div>
          <button type="submit" disabled={loading} className="btn-hacker mt-4 font-bold tracking-widest">
             {loading ? 'SNIPING...' : 'EXECUTE SNIPE ONLY'}
          </button>
        </form>
      ) : (
      <form onSubmit={handleSniperSubmit} className="flex flex-col gap-4">
         <div className="max-h-[400px] overflow-y-auto pr-2 space-y-6">
           {sniperTokens.map((t, i) => (
             <div key={i} className="hacker-border p-4 hacker-bg border-hacker-muted">
                <div className="flex justify-between mb-2">
                  <span className="text-[10px] text-hacker-green font-bold">TOKEN_{i+1}</span>
                  {sniperTokens.length > 1 && (
                    <button type="button" onClick={() => setSniperTokens(sniperTokens.filter((_, idx) => idx !== i))} className="text-red-500 text-[10px]">REMOVE</button>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-hacker-muted">NAME</label>
                    <input className="input-hacker text-xs" value={t.name} onChange={e => {
                      const newT = [...sniperTokens]; newT[i].name = e.target.value; setSniperTokens(newT);
                    }} />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-hacker-muted">SYMBOL</label>
                    <input className="input-hacker text-xs" value={t.symbol} onChange={e => {
                      const newT = [...sniperTokens]; newT[i].symbol = e.target.value; setSniperTokens(newT);
                    }} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-hacker-muted">THRESHOLD (USD)</label>
                    <input type="number" className="input-hacker text-xs" value={t.threshold} onChange={e => {
                      const newT = [...sniperTokens]; newT[i].threshold = parseFloat(e.target.value); setSniperTokens(newT);
                    }} />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] text-hacker-muted">DEV BUY (SOL)</label>
                    <input type="number" step="0.001" className="input-hacker text-xs" value={t.devBuy} onChange={e => {
                      const newT = [...sniperTokens]; newT[i].devBuy = parseFloat(e.target.value); setSniperTokens(newT);
                    }} />
                  </div>
                </div>
             </div>
           ))}
         </div>
         <div className="flex gap-2">
           <button
             type="button"
             onClick={() => setSniperTokens([...sniperTokens, { name: '', symbol: '', description: '', threshold: 100, devBuy: 0.001 }])}
             className="btn-hacker flex-grow text-[10px] border-hacker-muted"
           >
             + ADD TOKEN CONFIG
           </button>
           <button
             type="submit"
             disabled={loading}
             className="btn-hacker flex-grow bg-hacker-green text-black font-bold tracking-widest"
           >
             {loading ? 'DEPLOYING...' : 'DEPLOY SNIPER ARRAY'}
           </button>
         </div>
      </form>
      )}
    </div>
  );
};

const Sell = ({ wallets, addLog }) => {
  const [percentage, setPercentage] = useState(100);
  const [delay, setDelay] = useState(1);

  const dumpAll = async () => {
    try {
      addLog(`Dumping ${percentage}% from all wallets...`);
      await axios.post(`${API_BASE}/sell/dump-all`, { percentage });
      addLog("Dump request sent.");
    } catch (err) {
      addLog(`[ERROR] Dump failed: ${err.message}`);
    }
  };

  const devDump = async () => {
    try {
      addLog("Executing Dev Dump All strategy...");
      await axios.post(`${API_BASE}/sell/dev-dump`);
      addLog("Dev dump request sent.");
    } catch (err) {
      addLog(`[ERROR] Dev dump failed: ${err.message}`);
    }
  };

  return (
    <div className="flex flex-col gap-8 h-full">
      <h2 className="text-xl font-bold flex items-center gap-2"><DollarSign size={20} /> EXIT_STRATEGY</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="p-6 border border-hacker-muted bg-hacker-muted bg-opacity-5">
           <h3 className="text-lg font-bold mb-4">MASS_EXIT</h3>
           <div className="flex flex-col gap-4">
             <div className="flex flex-col gap-1">
               <label className="text-xs text-hacker-muted">SELL PERCENTAGE: {percentage}%</label>
               <input type="range" className="w-full" value={percentage} onChange={e => setPercentage(e.target.value)} />
             </div>
             <button onClick={dumpAll} className="btn-hacker py-4 bg-red-900 border-red-500 text-white hover:bg-red-600">
               EXECUTE DUMP ALL
             </button>
           </div>
        </div>
        <div className="p-6 border border-hacker-muted bg-hacker-muted bg-opacity-5">
           <h3 className="text-lg font-bold mb-4">DELAYED_EXIT</h3>
           <div className="flex flex-col gap-4">
             <div className="flex flex-col gap-1">
               <label className="text-xs text-hacker-muted">DELAY BETWEEN WALLETS (SEC): {delay}</label>
               <input type="number" className="input-hacker" value={delay} onChange={e => setDelay(e.target.value)} />
             </div>
             <button
                onClick={async () => {
                  try {
                    addLog(`Initiating delayed sell with ${delay}s interval...`);
                    await axios.post(`${API_BASE}/sell/delayed`, { delay });
                    addLog("Delayed sell initiated.");
                  } catch (e) { addLog(`[ERROR] Delayed sell failed: ${e.message}`); }
                }}
                className="btn-hacker py-4 border-yellow-500 text-yellow-500 hover:bg-yellow-500 hover:text-black"
             >
               EXECUTE DELAYED SELL
             </button>
           </div>
        </div>

        <div className="p-6 border border-hacker-muted bg-hacker-muted bg-opacity-5">
           <h3 className="text-lg font-bold mb-4">STRATEGIC_LIQUIDATION</h3>
           <div className="flex flex-col gap-4">
             <button onClick={devDump} className="btn-hacker py-4 flex flex-col items-center gap-1">
               <span className="font-bold">DEV DUMP ALL</span>
               <span className="text-[10px] opacity-50">Transfer to main then sell</span>
             </button>
             <button
                onClick={async () => {
                  const to = prompt("Enter target wallet address for transfer+sell:");
                  if (!to) return;
                  try {
                    addLog(`Executing transfer+sell to ${to}...`);
                    await axios.post(`${API_BASE}/sell/transfer-sell`, { to_wallet_address: to });
                    addLog("Transfer+sell protocol complete.");
                  } catch (e) { addLog(`[ERROR] Transfer+Sell failed: ${e.message}`); }
                }}
                className="btn-hacker py-4 border-cyan-500 text-cyan-500 hover:bg-cyan-500 hover:text-black flex flex-col items-center gap-1"
             >
                <span className="font-bold">TRANSFER SELL</span>
                <span className="text-[10px] opacity-50">Aggregate and sell from target</span>
             </button>
             <div className="text-[10px] text-hacker-muted italic text-center">
               Warning: This will aggregate all token balances before execution.
             </div>
           </div>
        </div>
      </div>
    </div>
  );
};

const Config = ({ addLog }) => {
  const [config, setConfig] = useState(null);

  useEffect(() => {
    axios.get(`${API_BASE}/config`).then(res => setConfig(res.data));
  }, []);

  const saveConfig = async () => {
    try {
      await axios.post(`${API_BASE}/config`, config);
      addLog("Configuration updated and system re-initialized.");
    } catch (err) {
      addLog(`[ERROR] Config save failed: ${err.message}`);
    }
  };

  if (!config) return null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-bold flex items-center gap-2"><Settings size={20} /> SYSTEM_PARAMETERS</h2>
        <button onClick={saveConfig} className="btn-hacker">SAVE CHANGES</button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 overflow-y-auto max-h-[400px] pr-4">
        {Object.entries(config.DEFAULT).map(([key, value]) => (
          <div key={key} className="flex flex-col gap-1">
            <label className="text-[10px] text-hacker-muted uppercase">{key.replace(/_/g, ' ')}</label>
            <input
              className="input-hacker text-xs"
              value={value}
              onChange={e => setConfig({
                ...config,
                DEFAULT: { ...config.DEFAULT, [key]: e.target.value }
              })}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default App;
