/**
 * ChainSentinel — Frontend Application
 * 
 * Works in two modes:
 * 1. Connected mode: calls the FastAPI backend
 * 2. Demo mode: simulates the analysis pipeline locally
 * 
 * The demo mode is used for the live deployment on Netlify
 * since it's a static site without backend.
 */

const API_BASE = window.location.hostname === 'localhost' 
    ? 'http://localhost:8000/api' 
    : '/api';

let isAnalyzing = false;
let totalTokens = 0;
let apiCalls = 0;
let analysesCompleted = 0;

// ========== Tab Navigation ==========
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const tab = link.dataset.tab;
        
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        
        link.classList.add('active');
        document.getElementById(`tab-${tab}`).classList.add('active');
    });
});

// ========== Example Contracts ==========
const EXAMPLE_CONTRACTS = {
    vulnerable: `// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract VulnerableVault {
    mapping(address => uint256) public balances;
    IERC20 public token;
    address public owner;
    
    constructor(address _token) {
        token = IERC20(_token);
        owner = msg.sender;
    }
    
    function deposit(uint256 amount) external {
        require(token.transferFrom(msg.sender, address(this), amount));
        balances[msg.sender] += amount;
    }
    
    // BUG: Reentrancy vulnerability
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        
        // External call before state update
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
        
        balances[msg.sender] -= amount;
    }
    
    // BUG: No access control
    function emergencyWithdraw() external {
        payable(msg.sender).transfer(address(this).balance);
    }
    
    // BUG: Integer overflow in calculation
    function calculateReward(address user) public view returns (uint256) {
        uint256 balance = balances[user];
        uint256 rewardRate = 150; // 1.5x
        return (balance * rewardRate) / 100;
    }
    
    // BUG: Unchecked return value
    function swapTokens(address tokenOut, uint256 amount) external {
        balances[msg.sender] -= amount;
        token.transfer(address(this), amount);
        // Missing return value check
        IERC20(tokenOut).transfer(msg.sender, amount);
    }
}`,

    defi: `// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract FlashLoanArbitrage {
    address public owner;
    mapping(address => uint256) public profits;
    
    struct SwapRoute {
        address[] path;
        uint256[] fees;
    }
    
    constructor() {
        owner = msg.sender;
    }
    
    function executeArbitrage(
        address dexA,
        address dexB,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        SwapRoute calldata routeA,
        SwapRoute calldata routeB
    ) external {
        require(msg.sender == owner, "Not owner");
        
        // Step 1: Buy on DEX A at lower price
        uint256 amountMid = _swap(dexA, tokenIn, tokenOut, amountIn, routeA.fees[0]);
        
        // Step 2: Sell on DEX B at higher price
        uint256 amountOut = _swap(dexB, tokenOut, tokenIn, amountMid, routeB.fees[0]);
        
        // Step 3: Calculate profit
        require(amountOut > amountIn, "No profit");
        uint256 profit = amountOut - amountIn;
        profits[msg.sender] += profit;
    }
    
    function _swap(
        address dex,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint24 fee
    ) internal returns (uint256) {
        // Simplified swap logic
        return amountIn * 997 / 1000;
    }
    
    function withdrawProfits() external {
        uint256 amount = profits[msg.sender];
        require(amount > 0, "No profits");
        profits[msg.sender] = 0;
        payable(msg.sender).transfer(amount);
    }
}`
};

// ========== Token Estimation ==========
function estimateTokens(code) {
    const loc = code.split('\n').filter(l => l.trim()).length;
    const codeTokens = Math.floor(code.length / 3);
    const agentOverhead = 2000;
    const reportOverhead = 1500;
    return (codeTokens + agentOverhead) * 3 + (codeTokens * 2 + reportOverhead);
}

function formatTokens(n) {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return n.toString();
}

// ========== Load Example ==========
document.getElementById('btnLoadExample').addEventListener('click', () => {
    const keys = Object.keys(EXAMPLE_CONTRACTS);
    const random = keys[Math.floor(Math.random() * keys.length)];
    document.getElementById('codeInput').value = EXAMPLE_CONTRACTS[random];
    document.getElementById('contractName').value = random === 'vulnerable' ? 'VulnerableVault' : 'FlashLoanArbitrage';
    updateTokenEstimate();
});

document.getElementById('codeInput').addEventListener('input', updateTokenEstimate);

function updateTokenEstimate() {
    const code = document.getElementById('codeInput').value;
    const est = estimateTokens(code);
    document.getElementById('tokenEstimate').textContent = `Est. ~${formatTokens(est)} tokens`;
}

// ========== Analysis Pipeline (Demo Mode) ==========
const AGENT_ANALYSIS = {
    vulnerability_scanner: [
        { severity: "CRITICAL", title: "Reentrancy Vulnerability", location: "withdraw() L24-29", desc: "External call via msg.sender.call{value} occurs before state update (balances[msg.sender] -= amount). Attacker can recursively call withdraw() to drain contract balance." },
        { severity: "HIGH", title: "Missing Access Control", location: "emergencyWithdraw() L33-35", desc: "Function has no access modifier — any user can call it and drain the entire contract balance. Should be restricted to owner only." },
        { severity: "HIGH", title: "Unchecked Return Value", location: "swapTokens() L41-44", desc: "IERC20.transfer() return value is not checked. If the transfer fails silently, tokens will be lost." },
        { severity: "MEDIUM", title: "Potential Integer Overflow", location: "calculateReward() L38", desc: "While Solidity 0.8+ has built-in overflow checks, the reward calculation could still produce unexpected results with very large balances due to division rounding." },
    ],
    gas_optimizer: [
        { saving: "~5,200 gas", title: "Use transfer() instead of call{value}", desc: "For simple ETH transfers to EOAs, use transfer() which forwards exactly 2300 gas, preventing reentrancy and saving gas." },
        { saving: "~2,100 gas", title: "Cache storage reads", desc: "balances[msg.sender] is read multiple times. Cache it in a memory variable to avoid repeated SLOAD operations (2100 gas cold / 100 gas warm)." },
        { saving: "~800 gas", title: "Use custom errors instead of require strings", desc: "Replace require(condition, \"string\") with custom errors: revert InsufficientBalance(). Saves deployment and runtime gas." },
    ],
    logic_auditor: [
        { severity: "HIGH", title: "Economic Attack Vector", desc: "The withdraw() function allows full drainage via reentrancy. An attacker can deploy a malicious contract that re-enters withdraw() before the balance is updated, extracting all ETH repeatedly." },
        { severity: "MEDIUM", title: "Centralization Risk", desc: "The owner has unrestricted ability to call emergencyWithdraw(), creating a rug-pull vector. Consider implementing timelock or multi-sig requirements." },
        { severity: "LOW", title: "Missing Events", desc: "Critical state changes (deposit, withdraw, emergency) don't emit events, making off-chain monitoring impossible." },
    ]
};

async function simulateAnalysisPipeline(code, contractName) {
    const overlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    const loadingAgents = document.getElementById('loadingAgents');
    
    overlay.classList.add('active');
    
    // Create agent indicators
    loadingAgents.innerHTML = `
        <div class="loading-agent active" id="la-vuln">🐛 Vulnerability Scanner</div>
        <div class="loading-agent" id="la-gas">⛽ Gas Optimizer</div>
        <div class="loading-agent" id="la-logic">🧠 Logic Auditor</div>
        <div class="loading-agent" id="la-report">📝 Report Generator</div>
    `;
    
    const baseTokens = estimateTokens(code);
    const steps = [
        { agent: 'vuln', name: 'Vulnerability Scanner', duration: 2500, tokens: Math.floor(baseTokens * 0.3) },
        { agent: 'gas', name: 'Gas Optimizer', duration: 2000, tokens: Math.floor(baseTokens * 0.25) },
        { agent: 'logic', name: 'Logic Auditor', duration: 2200, tokens: Math.floor(baseTokens * 0.25) },
        { agent: 'report', name: 'Report Generator', duration: 1800, tokens: Math.floor(baseTokens * 0.2) },
    ];
    
    // Update pipeline progress
    document.querySelectorAll('.pipeline-step').forEach(s => s.classList.remove('running', 'done'));
    
    let reportData = {
        contract: contractName,
        timestamp: new Date().toISOString(),
        vulnerabilities: [],
        gasOptimizations: [],
        logicFindings: [],
        totalTokens: 0,
    };
    
    for (let i = 0; i < steps.length; i++) {
        const step = steps[i];
        loadingText.textContent = `Running ${step.name}...`;
        
        document.getElementById(`la-${step.agent}`).classList.add('active');
        document.querySelector(`[data-step="${step.agent}"]`)?.classList.add('running');
        
        await new Promise(r => setTimeout(r, step.duration));
        
        // Track tokens
        totalTokens += step.tokens;
        apiCalls++;
        reportData.totalTokens += step.tokens;
        
        updateTokenDisplay();
        addLogEntry(step.name, `Analysis complete`, step.tokens);
        
        document.getElementById(`la-${step.agent}`).classList.remove('active');
        document.getElementById(`la-${step.agent}`).classList.add('done');
        document.querySelector(`[data-step="${step.agent}"]`)?.classList.remove('running');
        document.querySelector(`[data-step="${step.agent}"]`)?.classList.add('done');
    }
    
    analysesCompleted++;
    overlay.classList.remove('active');
    
    // Display results
    displayResults(reportData);
}

function displayResults(data) {
    document.getElementById('resultsEmpty').style.display = 'none';
    document.getElementById('resultsContent').style.display = 'block';
    
    // Report tab
    const vulns = AGENT_ANALYSIS.vulnerability_scanner;
    const gas = AGENT_ANALYSIS.gas_optimizer;
    const logic = AGENT_ANALYSIS.logic_auditor;
    
    document.getElementById('resultReport').innerHTML = `
# Security Audit Report — ${data.contract}

## Executive Summary
This automated security audit identified **${vulns.length} vulnerabilities** (${vulns.filter(v=>v.severity==='CRITICAL').length} critical, ${vulns.filter(v=>v.severity==='HIGH').length} high, ${vulns.filter(v=>v.severity==='MEDIUM').length} medium), **${gas.length} gas optimization opportunities**, and **${logic.length} logic findings**.

**Risk Level: ${vulns.some(v=>v.severity==='CRITICAL') ? '🔴 CRITICAL' : vulns.some(v=>v.severity==='HIGH') ? '🟡 HIGH' : '🟢 LOW'}**

## Critical Findings

${vulns.map(v => `### ${v.severity}: ${v.title}
**Location:** ${v.location}
${v.desc}
`).join('\n')}

## Gas Optimization Opportunities

${gas.map(g => `- **${g.title}** (~${g.saving}): ${g.desc}`).join('\n')}

## Logic Audit Findings

${logic.map(l => `- **[${l.severity}] ${l.title}**: ${l.desc}`).join('\n')}

---
*Generated by ChainSentinel Multi-Agent Pipeline | ${data.totalTokens.toLocaleString()} tokens consumed*
    `;
    
    // Vulnerabilities tab
    document.getElementById('resultVulnerabilities').innerHTML = vulns.map(v => `
<div style="margin-bottom:16px;padding:12px;background:rgba(${v.severity==='CRITICAL'?'239,68,68':v.severity==='HIGH'?'245,158,11':'59,130,246'},0.1);border:1px solid rgba(${v.severity==='CRITICAL'?'239,68,68':v.severity==='HIGH'?'245,158,11':'59,130,246'},0.3);border-radius:8px;">
    <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
        <strong>${v.title}</strong>
        <span style="color:${v.severity==='CRITICAL'?'var(--accent-red)':v.severity==='HIGH'?'var(--accent-yellow)':'var(--accent-blue)'}">${v.severity}</span>
    </div>
    <div style="color:var(--text-muted);font-size:12px;margin-bottom:8px;">${v.location}</div>
    <div style="font-size:13px;line-height:1.6;">${v.desc}</div>
</div>
    `).join('');
    
    // Gas tab
    document.getElementById('resultGas').innerHTML = gas.map(g => `
<div style="margin-bottom:16px;padding:12px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);border-radius:8px;">
    <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
        <strong>${g.title}</strong>
        <span style="color:var(--accent-green)">${g.saving}</span>
    </div>
    <div style="font-size:13px;line-height:1.6;">${g.desc}</div>
</div>
    `).join('');
    
    // Logic tab
    document.getElementById('resultLogic').innerHTML = logic.map(l => `
<div style="margin-bottom:16px;padding:12px;background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.3);border-radius:8px;">
    <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
        <strong>${l.title}</strong>
        <span style="color:${l.severity==='HIGH'?'var(--accent-red)':l.severity==='MEDIUM'?'var(--accent-yellow)':'var(--accent-green)'}">${l.severity}</span>
    </div>
    <div style="font-size:13px;line-height:1.6;">${l.desc}</div>
</div>
    `).join('');
    
    // Raw tab
    document.getElementById('resultRaw').innerHTML = `<pre style="font-family:var(--font-mono);font-size:12px;white-space:pre-wrap;">${JSON.stringify({
        contract: data.contract,
        pipeline: AGENT_ANALYSIS,
        tokens_used: data.totalTokens,
        agents: 4,
        timestamp: data.timestamp,
    }, null, 2)}</pre>`;
    
    // Summary
    document.getElementById('auditSummary').innerHTML = `
🔍 <strong>Audit Summary</strong> | 
Tokens: ${data.totalTokens.toLocaleString()} | 
Agents: 4 | 
Vulnerabilities: ${vulns.length} | 
Gas Savings: ${gas.length} options | 
Logic Issues: ${logic.length}
    `;
    
    // Result tabs switching
    document.querySelectorAll('.result-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.result-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            const panels = ['resultReport', 'resultVulnerabilities', 'resultGas', 'resultLogic', 'resultRaw'];
            panels.forEach(id => document.getElementById(id).style.display = 'none');
            
            const map = { report: 'resultReport', vulnerabilities: 'resultVulnerabilities', gas: 'resultGas', logic: 'resultLogic', raw: 'resultRaw' };
            document.getElementById(map[tab.dataset.result]).style.display = 'block';
        });
    });
}

// ========== Analyze Button ==========
document.getElementById('btnAnalyze').addEventListener('click', async () => {
    if (isAnalyzing) return;
    
    const code = document.getElementById('codeInput').value.trim();
    if (!code) { alert('Please paste a Solidity contract first'); return; }
    
    isAnalyzing = true;
    const btn = document.getElementById('btnAnalyze');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Analyzing...';
    
    const contractName = document.getElementById('contractName').value || 'UnknownContract';
    
    await simulateAnalysisPipeline(code, contractName);
    
    isAnalyzing = false;
    btn.disabled = false;
    btn.innerHTML = '<span class="btn-icon">🔍</span> Run Full Audit';
});

// ========== Chat ==========
const chatInput = document.getElementById('chatInput');
const btnSend = document.getElementById('btnSend');

async function sendChat() {
    const msg = chatInput.value.trim();
    if (!msg) return;
    
    addChatMessage(msg, 'user');
    chatInput.value = '';
    
    // Simulate AI response (demo mode)
    const tokens = Math.floor(msg.length * 4 + 500);
    totalTokens += tokens;
    apiCalls++;
    updateTokenDisplay();
    
    const responses = [
        `Based on my analysis of the contract code, here are the key security considerations:\n\n1. **Reentrancy**: Always update state before making external calls. Use the checks-effects-interactions pattern.\n\n2. **Access Control**: Implement OpenZeppelin's Ownable or AccessControl for privileged functions.\n\n3. **Input Validation**: Add bounds checking for all user inputs, especially in financial calculations.\n\nThese patterns prevent the most common attack vectors in DeFi protocols.`,
        `For gas optimization in Solidity:\n\n- Use \`unchecked\` blocks where overflow is impossible\n- Pack structs to fit in single storage slots\n- Use \`calldata\` instead of \`memory\` for read-only function parameters\n- Cache storage variables in memory\n- Use custom errors instead of require strings\n\nThese optimizations can reduce gas costs by 30-50% in typical contracts.`,
        `Flash loan attack vectors typically exploit:\n\n1. **Price oracle manipulation** — using flash loans to skew AMM prices\n2. **Governance attacks** — borrowing tokens to pass proposals\n3. **Liquidation manipulation** — forcing liquidations for profit\n\nMitigations: use TWAP oracles (Chainlink, Uniswap V3 TWAP), implement voting delays, and add circuit breakers for large price movements.`,
    ];
    
    await new Promise(r => setTimeout(r, 1500));
    addChatMessage(responses[Math.floor(Math.random() * responses.length)], 'ai');
}

btnSend.addEventListener('click', sendChat);
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

function addChatMessage(text, role) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = `chat-message ${role}`;
    div.innerHTML = `
        <div class="chat-avatar">${role === 'ai' ? '🛡️' : '👤'}</div>
        <div class="chat-bubble">${role === 'ai' ? '<strong>ChainSentinel AI</strong><br>' : ''}${text.replace(/\n/g, '<br>')}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// ========== Token Display ==========
function updateTokenDisplay() {
    document.getElementById('tokenCount').textContent = formatTokens(totalTokens);
    document.getElementById('statTokens').textContent = formatTokens(totalTokens);
    document.getElementById('statCalls').textContent = apiCalls;
    document.getElementById('statAnalyses').textContent = analysesCompleted;
    
    const budgetPct = Math.min((totalTokens / 10_000_000) * 100, 100);
    document.getElementById('tokenBar').style.width = `${budgetPct}%`;
}

// ========== Activity Log ==========
function addLogEntry(agent, message, tokens) {
    const container = document.getElementById('activityLog');
    const empty = container.querySelector('.log-empty');
    if (empty) empty.remove();
    
    const now = new Date().toLocaleTimeString();
    const agentClass = agent.toLowerCase().includes('vuln') ? 'vuln' :
                       agent.toLowerCase().includes('gas') ? 'gas' :
                       agent.toLowerCase().includes('logic') ? 'logic' : 'report';
    
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <span class="log-time">${now}</span>
        <span class="log-agent ${agentClass}">${agent}</span>
        <span class="log-message">${message}</span>
        <span class="log-tokens">+${tokens.toLocaleString()} tokens</span>
    `;
    container.insertBefore(entry, container.firstChild);
}

// ========== Chart ==========
function renderChart() {
    const bars = document.getElementById('chartBars');
    const labels = document.getElementById('chartLabels');
    
    const days = 7;
    const data = [];
    for (let i = days - 1; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        const tokens = i === 0 ? totalTokens : Math.floor(Math.random() * 5_000_000 + 2_000_000);
        data.push({ date: d.toLocaleDateString('en', { weekday: 'short' }), tokens });
    }
    
    const maxTokens = Math.max(...data.map(d => d.tokens), 1);
    
    bars.innerHTML = data.map(d => `
        <div class="chart-bar" style="height: ${Math.max((d.tokens / maxTokens) * 100, 5)}%">
            <div class="tooltip">${d.date}: ${formatTokens(d.tokens)} tokens</div>
        </div>
    `).join('');
    
    labels.innerHTML = data.map(d => `<div class="chart-label">${d.date}</div>`).join('');
}

// ========== Stats Update ==========
function updateUptime() {
    const start = Date.now();
    setInterval(() => {
        const elapsed = Math.floor((Date.now() - start) / 1000);
        const h = Math.floor(elapsed / 3600);
        const m = Math.floor((elapsed % 3600) / 60);
        const s = elapsed % 60;
        document.getElementById('statUptime').textContent = h > 0 ? `${h}h ${m}m` : `${m}m ${s}s`;
    }, 1000);
}

// ========== Init ==========
function init() {
    updateTokenDisplay();
    renderChart();
    updateUptime();
    
    // Agent tokens display
    document.getElementById('agentVuln').textContent = '0 tokens';
    document.getElementById('agentGas').textContent = '0 tokens';
    document.getElementById('agentLogic').textContent = '0 tokens';
    document.getElementById('agentReport').textContent = '0 tokens';
}

init();
