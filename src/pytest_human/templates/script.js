let searchResults = [];
let currentResultIndex = -1;

document.addEventListener('keydown', function (event) {
    const searchInput = document.getElementById('search-input');
    if (event.key === '/') {
        event.preventDefault();
        searchInput.focus();
    } else if (event.key === 'Escape') {
        searchInput.blur();
    } else if (event.key === 'Enter' && document.activeElement === searchInput) {
        event.preventDefault();
        if (event.shiftKey) {
            prevResult();
        } else {
            nextResult();
        }
    }
});

function removeHighlights(rootElement) {
    const highlights = rootElement.querySelectorAll('.highlight');
    for (let i = highlights.length - 1; i >= 0; i--) {
        const highlight = highlights[i];
        const parent = highlight.parentNode;
        while (highlight.firstChild) {
            parent.insertBefore(highlight.firstChild, highlight);
        }
        parent.removeChild(highlight);
        parent.normalize();
    }
}

function getTextNodes(rootElement) {
    const walker = document.createTreeWalker(rootElement, NodeFilter.SHOW_TEXT, null, false);
    const textNodes = [];
    let currentNode;
    while (currentNode = walker.nextNode()) {
        const isSearchableCell = currentNode.parentNode.closest('td.msg-cell, td.source-cell, td.level-cell, td.time-cell');
        if (currentNode.nodeValue.length > 0 && isSearchableCell) {
            textNodes.push(currentNode);
        }
    }

    return textNodes;
}

function runSearchRegex(query, fullText) {
    // Replace spaces with \s to handle all whitespace types (spaces, &nbsp;, etc.)
    const finalPattern = query.replace(/ /g, '\\s');
    const regex = new RegExp(finalPattern, 'gi');

    let match;
    const matches = [];
    while ((match = regex.exec(fullText)) !== null) {
        if (match[0].length === 0) continue;
        matches.push({
            start: match.index,
            end: match.index + match[0].length,
        });
    }

    return matches;
}

function searchLogs() {
    clearSearchState();
    const searchInput = document.getElementById('search-input');
    const query = searchInput.value;

    if (query.length > 0) {
        document.getElementById('clear-search-btn').style.visibility = 'visible';
    } else {
        document.getElementById('clear-search-btn').style.visibility = 'hidden';
    }

    if (query.length < 2) {
        updateSearchCounter();
        return;
    }

    try {
        const logContainer = document.querySelector('.log-container');
        const textNodes = getTextNodes(logContainer);
        const fullText = textNodes.map(node => node.nodeValue).join('');
        const matches = runSearchRegex(query, fullText);

        searchResults = highlightMatches(matches, textNodes);

        if (searchResults.length > 0) {
            currentResultIndex = 0;
            scrollToResult(searchResults[0]);
        }
        updateSearchCounter();
    }
    catch (e) {
        console.error("Search Error:", e);
        searchInput.classList.add('search-error');
    } finally {
        updateSearchCounter();
    }
}

function clearSearchText() {
    const searchInput = document.getElementById('search-input');
    const clearButton = document.getElementById('clear-search-btn');
    searchInput.value = '';
    clearButton.style.display = 'none';
    clearSearchState();
    updateSearchCounter();
    searchInput.focus();
}

function clearSearchState() {
    document.getElementById('search-input').classList.remove('search-error');
    searchResults = [];
    currentResultIndex = -1;
    const logContainer = document.querySelector('.log-container');
    removeHighlights(logContainer);
}

function highlightMatches(matches, textNodes) {
    let textOffset = 0;
    const nodePositions = textNodes.map(node => {
        const start = textOffset;
        textOffset += node.nodeValue.length;
        return { node, start, end: textOffset };
    });

    // Process matches in reverse to avoid DOM modification issues
    for (let i = matches.length - 1; i >= 0; i--) {
        const currentMatch = matches[i];
        const affectedNodes = nodePositions.filter(pos =>
            pos.start < currentMatch.end && pos.end > currentMatch.start
        );

        const matchFragments = [];

        affectedNodes.forEach((pos, index) => {
            const node = pos.node;
            const parent = node.parentNode;
            const highlightStart = Math.max(0, currentMatch.start - pos.start);
            const highlightEnd = Math.min(node.nodeValue.length, currentMatch.end - pos.start);

            if (highlightStart >= highlightEnd) return;

            const middlePart = node.splitText(highlightStart);
            middlePart.splitText(highlightEnd - highlightStart);

            const highlight = document.createElement('span');
            highlight.className = 'highlight';
            highlight.dataset.matchId = i; // Group fragments of the same match
            highlight.appendChild(middlePart.cloneNode(true));
            parent.replaceChild(highlight, middlePart);

            if (index === 0) {
                highlight.classList.add('highlight-start');
            }
            if (index === affectedNodes.length - 1) {
                highlight.classList.add('highlight-end');
            }
            matchFragments.unshift(highlight);
        });

        if (matchFragments.length > 0) {
            searchResults.unshift(matchFragments[0]);
        }
    }
    return searchResults;
}

function updateSearchCounter() {
    const counter = document.getElementById('search-counter');
    if (searchResults.length > 0) {
        counter.textContent = `${currentResultIndex + 1} / ${searchResults.length}`;
    } else if (document.getElementById('search-input').value.length >= 2) {
        counter.textContent = `0 / 0`;
    } else {
        counter.textContent = '';
    }
}

function expandParents(element) {
    let current = element;
    while (current && current !== document.body) {
        if (current.classList.contains('nested-block') && current.style.display === 'none') {
            const header = document.getElementById('header_' + current.id);
            if (header) {
                const toggleButton = header.querySelector('.toggle-cell');
                if (toggleButton) {
                    toggle(current.id);
                }
            }
        }
        current = current.parentElement;
    }
}

function removeActiveHighlights() {
    const previouslyActive = document.querySelectorAll('.highlight.active');
    previouslyActive.forEach(el => el.classList.remove('active'));
}

function scrollToResult(element) {
    expandParents(element);
    removeActiveHighlights();

    const matchId = element.dataset.matchId;
    if (matchId) {
        const allFragmentsForMatch = document.querySelectorAll(`.highlight[data-match-id='${matchId}']`);
        allFragmentsForMatch.forEach(el => el.classList.add('active'));
    }

    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    updateSearchCounter();
}

function nextResult() {
    if (searchResults.length > 0) {
        currentResultIndex = (currentResultIndex + 1) % searchResults.length;
        scrollToResult(searchResults[currentResultIndex]);
    }
}

function prevResult() {
    if (searchResults.length > 0) {
        currentResultIndex = (currentResultIndex - 1 + searchResults.length) % searchResults.length;
        scrollToResult(searchResults[currentResultIndex]);
    }
}

function toggle(id) {
    const e = document.getElementById(id);
    const t = document.getElementById('toggle-' + id);
    if (e.style.display === 'none') {
        e.style.display = 'table-row';
        e.setAttribute('aria-expanded', 'true');
        // endash for width consistency
        t.textContent = '[–]';
    } else {
        e.style.display = 'none';
        e.setAttribute('aria-expanded', 'false');
        t.textContent = '[+]';
    }
}

function formatDuration(ms) {
    if (ms < 1000) {
        return `${Math.round(ms)} ms`;
    }
    const seconds = ms / 1000;
    if (seconds < 60) {
        return `${seconds.toFixed(1)} s`;
    }
    const minutes = seconds / 60;
    if (minutes < 60) {
        return `${minutes.toFixed(1)} m`;
    }
    const hours = minutes / 60;
    return `${hours.toFixed(1)} h`;
}

function finalizeSpan(blockId, durationId, durationMs) {
    const durationCell = document.getElementById(durationId);
    if (durationCell) {
        durationCell.textContent = formatDuration(durationMs);
    }

    const contentRow = document.getElementById(blockId);
    if (!contentRow) return;

    const innerTable = contentRow.querySelector('table.log-table');
    if (innerTable && innerTable.rows.length === 0) {
        const headerRow = contentRow.previousElementSibling;
        if (headerRow) {
            const toggleCell = headerRow.querySelector('.toggle-cell');
            if (toggleCell) {
                toggleCell.style.visibility = 'hidden';
                toggleCell.style.cursor = 'default';
            }
        }
    }
}

function setSpanSeverity(blockId, cssClass) {
    const headerRow = document.getElementById('header_' + blockId);
    if (!headerRow) return;
    const classesToRemove = Array.from(headerRow.classList).filter(c => c.startsWith('log-level-'));
    for (const c of classesToRemove) {
        headerRow.classList.remove(c);
    }
    headerRow.classList.add(cssClass);
}
