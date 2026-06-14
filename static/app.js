/**
 * TrendPulse — Frontend Logic
 * Handles scan triggering, SSE progress, and result rendering.
 */

let isScanning = false;

function startScan() {
    if (isScanning) return;
    isScanning = true;

    const btn = document.getElementById('scan-btn');
    const progressSection = document.getElementById('progress-section');
    const resultsSection = document.getElementById('results-section');
    const progressLog = document.getElementById('progress-log');
    const progressText = document.getElementById('progress-text');

    // Reset UI
    btn.classList.add('scanning');
    btn.querySelector('.scan-btn-text').textContent = 'Scanning...';
    progressSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    progressLog.innerHTML = '';

    // Hide all result sub-sections
    document.getElementById('summary-card').classList.add('hidden');
    document.getElementById('ideas-section').classList.add('hidden');
    document.getElementById('reddit-section').classList.add('hidden');
    document.getElementById('x-section').classList.add('hidden');

    // Update timestamp
    document.getElementById('timestamp').textContent = `Scanning at ${new Date().toLocaleTimeString()}`;

    // Start SSE connection
    const eventSource = new EventSource('/api/scan');

    eventSource.addEventListener('progress', (e) => {
        const msg = e.data;
        progressText.textContent = msg;
        addLogEntry(progressLog, msg);
    });

    eventSource.addEventListener('result', (e) => {
        const data = JSON.parse(e.data);
        renderResults(data);

        // Finish up
        eventSource.close();
        isScanning = false;
        btn.classList.remove('scanning');
        btn.querySelector('.scan-btn-text').textContent = 'Scan Again';
        progressText.textContent = 'Done!';
        document.getElementById('timestamp').textContent = `Last scan: ${new Date().toLocaleTimeString()}`;

        // Auto scroll to results
        setTimeout(() => {
            document.getElementById('results-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 300);
    });

    eventSource.addEventListener('error_msg', (e) => {
        addLogEntry(progressLog, `⚠ Error: ${e.data}`);
    });

    eventSource.onerror = () => {
        eventSource.close();
        isScanning = false;
        btn.classList.remove('scanning');
        btn.querySelector('.scan-btn-text').textContent = 'Scan for Trends';
        progressText.textContent = 'Connection lost. Try again.';
    };
}

function addLogEntry(container, message) {
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    entry.textContent = `[${time}] ${message}`;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function renderResults(data) {
    const resultsSection = document.getElementById('results-section');
    resultsSection.classList.remove('hidden');

    // Render summary
    if (data.trend_summary || data.summary_stats) {
        renderSummary(data.trend_summary, data.summary_stats);
    }

    // Render content ideas
    if (data.ideas && data.ideas.length > 0) {
        renderIdeas(data.ideas);
    }

    // Render Reddit posts
    if (data.top_reddit && data.top_reddit.length > 0) {
        renderRedditPosts(data.top_reddit);
    }

    // Render X tweets
    if (data.top_x && data.top_x.length > 0) {
        renderXTweets(data.top_x);
    }
}

function renderSummary(summary, stats) {
    const card = document.getElementById('summary-card');
    const summaryText = document.getElementById('trend-summary');
    const statsRow = document.getElementById('stats-row');

    card.classList.remove('hidden');
    summaryText.textContent = summary || 'Trends analyzed successfully.';

    statsRow.innerHTML = '';
    if (stats && Object.keys(stats).length > 0) {
        const chips = [
            { label: 'Reddit Posts', value: stats.total_reddit_posts || 0, icon: '📊' },
            { label: 'X Tweets', value: stats.total_x_tweets || 0, icon: '🐦' },
            { label: 'Top Subreddit', value: stats.top_subreddit || 'N/A', icon: '🏆' },
            { label: 'Top X Account', value: stats.top_x_account || 'N/A', icon: '⭐' },
        ];

        chips.forEach(chip => {
            const el = document.createElement('div');
            el.className = 'stat-chip';
            el.innerHTML = `${chip.icon} ${chip.label}: <span class="stat-value">${chip.value}</span>`;
            statsRow.appendChild(el);
        });
    }

    // Show retry button if Gemini failed
    const retryBtn = document.getElementById('retry-ai-btn');
    if (summary && (summary.includes('Error:') || summary.includes('⚠') || summary.includes('UNAVAILABLE'))) {
        retryBtn.classList.remove('hidden');
    } else {
        retryBtn.classList.add('hidden');
    }
}

function startRetryAI() {
    if (isScanning) return;
    isScanning = true;

    const retryBtn = document.getElementById('retry-ai-btn');
    const mainBtn = document.getElementById('scan-btn');
    const progressSection = document.getElementById('progress-section');
    const progressLog = document.getElementById('progress-log');
    const progressText = document.getElementById('progress-text');

    // UI Feedback
    retryBtn.classList.add('scanning');
    retryBtn.querySelector('.scan-btn-text').textContent = 'Retrying...';
    mainBtn.classList.add('scanning');
    progressSection.classList.remove('hidden');
    progressLog.innerHTML = '';
    document.getElementById('ideas-section').classList.add('hidden');

    addLogEntry(progressLog, "Starting AI generation retry using cached data...");

    const eventSource = new EventSource('/api/retry_ai');

    eventSource.addEventListener('progress', (e) => {
        const msg = e.data;
        progressText.textContent = msg;
        addLogEntry(progressLog, msg);
    });

    eventSource.addEventListener('result', (e) => {
        const data = JSON.parse(e.data);
        renderResults(data);

        eventSource.close();
        isScanning = false;
        retryBtn.classList.remove('scanning');
        retryBtn.querySelector('.scan-btn-text').textContent = 'Retry AI Generation';
        mainBtn.classList.remove('scanning');
        progressText.textContent = 'Done!';
        
        setTimeout(() => {
            document.getElementById('summary-card').scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 300);
    });

    eventSource.addEventListener('error_msg', (e) => {
        addLogEntry(progressLog, `⚠ Error: ${e.data}`);
    });

    eventSource.onerror = () => {
        eventSource.close();
        isScanning = false;
        retryBtn.classList.remove('scanning');
        retryBtn.querySelector('.scan-btn-text').textContent = 'Retry AI Generation';
        mainBtn.classList.remove('scanning');
        progressText.textContent = 'Connection lost. Try again.';
    };
}

function renderIdeas(ideas) {
    const section = document.getElementById('ideas-section');
    const grid = document.getElementById('ideas-grid');

    section.classList.remove('hidden');
    grid.innerHTML = '';

    ideas.forEach((idea, index) => {
        const card = document.createElement('div');
        card.className = 'idea-card glass-card';
        card.style.animationDelay = `${index * 0.08}s`;

        const talkingPoints = (idea.talking_points || [])
            .map(tp => `<li>${escapeHtml(tp)}</li>`)
            .join('');

        const sources = (idea.source_trends || [])
            .map(s => `<span class="idea-source">${escapeHtml(s)}</span>`)
            .join('');

        card.innerHTML = `
            <div class="idea-number">${index + 1}</div>
            <h3 class="idea-title">${escapeHtml(idea.title || '')}</h3>
            ${idea.hook ? `<p class="idea-hook">"${escapeHtml(idea.hook)}"</p>` : ''}
            <div class="idea-meta">
                ${idea.format ? `<span class="idea-format">${escapeHtml(idea.format)}</span>` : ''}
                ${sources}
            </div>
            ${idea.why_viral ? `<p class="idea-why">${escapeHtml(idea.why_viral)}</p>` : ''}
            ${talkingPoints ? `<ul class="idea-points">${talkingPoints}</ul>` : ''}
        `;

        grid.appendChild(card);
    });
}

function renderRedditPosts(posts) {
    const section = document.getElementById('reddit-section');
    const grid = document.getElementById('reddit-grid');

    section.classList.remove('hidden');
    grid.innerHTML = '';

    posts.forEach((post, index) => {
        const card = document.createElement('div');
        card.className = 'post-card glass-card';
        card.style.animationDelay = `${index * 0.05}s`;

        const viralityWidth = post.normalized_score || 0;

        card.innerHTML = `
            <span class="post-source-badge reddit">r/${escapeHtml(post.subreddit || '')}</span>
            <div class="post-title">
                <a href="${escapeHtml(post.url || '#')}" target="_blank" rel="noopener">${escapeHtml(post.title || '')}</a>
            </div>
            <div class="post-stats">
                <span class="post-stat"><span class="stat-icon">⬆</span> ${formatNumber(post.score)}</span>
                <span class="post-stat"><span class="stat-icon">💬</span> ${formatNumber(post.comments)}</span>
                ${post.flair ? `<span class="post-stat">${escapeHtml(post.flair)}</span>` : ''}
            </div>
            <div class="virality-bar">
                <div class="virality-fill" style="width: ${viralityWidth}%"></div>
            </div>
        `;

        grid.appendChild(card);
    });
}

function renderXTweets(tweets) {
    const section = document.getElementById('x-section');
    const grid = document.getElementById('x-grid');

    section.classList.remove('hidden');
    grid.innerHTML = '';

    tweets.forEach((tweet, index) => {
        const card = document.createElement('div');
        card.className = 'post-card glass-card';
        card.style.animationDelay = `${index * 0.05}s`;

        const viralityWidth = tweet.normalized_score || 0;
        const truncatedText = (tweet.text || '').length > 220
            ? tweet.text.slice(0, 220) + '...'
            : tweet.text || '';

        card.innerHTML = `
            <span class="post-source-badge x">@${escapeHtml(tweet.handle || '')}</span>
            <div class="post-title">
                <a href="${escapeHtml(tweet.url || '#')}" target="_blank" rel="noopener">${escapeHtml(truncatedText)}</a>
            </div>
            <div class="post-stats">
                <span class="post-stat"><span class="stat-icon">❤️</span> ${formatNumber(tweet.likes)}</span>
                <span class="post-stat"><span class="stat-icon">🔄</span> ${formatNumber(tweet.retweets)}</span>
                <span class="post-stat"><span class="stat-icon">💬</span> ${formatNumber(tweet.replies)}</span>
                ${tweet.views ? `<span class="post-stat"><span class="stat-icon">👁</span> ${formatNumber(tweet.views)}</span>` : ''}
            </div>
            <div class="virality-bar">
                <div class="virality-fill" style="width: ${viralityWidth}%"></div>
            </div>
        `;

        grid.appendChild(card);
    });
}

// --- Utilities ---

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatNumber(num) {
    if (!num && num !== 0) return '0';
    num = parseInt(num, 10);
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}
