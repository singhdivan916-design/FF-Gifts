// static/js/script.js

let currentJwt = '';
let currentCategory = 'All';
let currentPage = 1;
let currentLimit = 24;
let isLoading = false;
let hasMore = true;
let allCategories = [];

// DOM elements
const loginBox = document.getElementById('loginBox');
const storeBox = document.getElementById('storeBox');
const loadBtn = document.getElementById('loadBtn');
const errorMsg = document.getElementById('errorMsg');
const itemsGrid = document.getElementById('itemsGrid');
const categoryBar = document.getElementById('categoryBar');
const valDiamond = document.getElementById('valDiamond');
const valGold = document.getElementById('valGold');
const valTopup = document.getElementById('valTopup');
const giftsSentSpan = document.getElementById('giftsSent');
const giftModal = document.getElementById('giftModal');
const targetUid = document.getElementById('targetUid');
const giftMsg = document.getElementById('giftMsg');
const confirmSendBtn = document.getElementById('confirmSend');

let selectedItem = null;
let currentMethod = 'direct'; // direct, access, eat, uid_password

// --- Auth method UI handling ---
const authMethodBtns = document.querySelectorAll('.auth-method-btn');
const authInputsDiv = document.getElementById('authInputs');

function updateAuthInputs() {
    let html = '';
    if (currentMethod === 'direct') {
        html = '<input type="text" id="jwtInput" placeholder="Paste your JWT token here..." autocomplete="off">';
    } else if (currentMethod === 'access') {
        html = '<input type="text" id="accessTokenInput" placeholder="Enter Access Token" autocomplete="off">';
    } else if (currentMethod === 'eat') {
        html = '<input type="text" id="eatTokenInput" placeholder="Enter EAT Token" autocomplete="off">';
    } else if (currentMethod === 'uid_password') {
        html = `
            <input type="text" id="uidInput" placeholder="Enter UID" autocomplete="off">
            <input type="password" id="passwordInput" placeholder="Enter Password" autocomplete="off" style="margin-top:10px;">
        `;
    }
    authInputsDiv.innerHTML = html;
}

authMethodBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        authMethodBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentMethod = btn.dataset.method;
        updateAuthInputs();
    });
});
updateAuthInputs(); // initial

function showError(msg) {
    errorMsg.innerText = msg;
    errorMsg.style.display = 'block';
    setTimeout(() => errorMsg.style.display = 'none', 5000);
}

// Authenticate using selected method, returns JWT
async function authenticate() {
    let payload = { method: currentMethod };
    if (currentMethod === 'direct') {
        const jwt = document.getElementById('jwtInput')?.value.trim();
        if (!jwt) throw new Error('JWT token is required');
        payload.jwt = jwt;
    } else if (currentMethod === 'access') {
        const token = document.getElementById('accessTokenInput')?.value.trim();
        if (!token) throw new Error('Access token is required');
        payload.access_token = token;
    } else if (currentMethod === 'eat') {
        const token = document.getElementById('eatTokenInput')?.value.trim();
        if (!token) throw new Error('EAT token is required');
        payload.eat_token = token;
    } else if (currentMethod === 'uid_password') {
        const uid = document.getElementById('uidInput')?.value.trim();
        const pwd = document.getElementById('passwordInput')?.value.trim();
        if (!uid || !pwd) throw new Error('UID and password are required');
        payload.uid = uid;
        payload.password = pwd;
    }

    const response = await fetch('/api/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!data.success) throw new Error(data.message || 'Authentication failed');
    return data.jwt;
}

// Load store from API
async function loadStore(resetPage = true) {
    if (isLoading) return;
    if (resetPage) {
        currentPage = 1;
        hasMore = true;
        itemsGrid.innerHTML = '';
    }
    isLoading = true;

    try {
        const response = await fetch('/api/get_store', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jwt: currentJwt,
                page: currentPage,
                limit: currentLimit,
                category: currentCategory
            })
        });
        const data = await response.json();
        if (!data.success) throw new Error(data.message || 'Failed to load store');

        valDiamond.innerHTML = `💎 ${data.wallet.diamond}`;
        valGold.innerHTML = `🪙 ${data.wallet.gold}`;
        valTopup.innerText = data.wallet.last_topup;
        giftsSentSpan.innerText = `🎁 Sent Today: ${data.sent_today}`;

        if (allCategories.length === 0 && data.categories) {
            allCategories = data.categories;
            buildCategoryBar();
        }

        if (resetPage) itemsGrid.innerHTML = '';
        data.items.forEach(item => addItemCard(item));

        hasMore = data.has_more;
        if (hasMore) currentPage++;
    } catch (err) {
        console.error(err);
        showError(err.message);
    } finally {
        isLoading = false;
    }
}

function buildCategoryBar() {
    categoryBar.innerHTML = '';
    const allBtn = document.createElement('button');
    allBtn.className = 'cat-btn' + (currentCategory === 'All' ? ' active' : '');
    allBtn.innerText = 'All Items';
    allBtn.dataset.cat = 'All';
    allBtn.addEventListener('click', () => switchCategory('All'));
    categoryBar.appendChild(allBtn);

    allCategories.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'cat-btn' + (currentCategory === cat ? ' active' : '');
        btn.innerText = cat;
        btn.dataset.cat = cat;
        btn.addEventListener('click', () => switchCategory(cat));
        categoryBar.appendChild(btn);
    });
}

function switchCategory(category) {
    if (currentCategory === category) return;
    currentCategory = category;
    currentPage = 1;
    hasMore = true;
    itemsGrid.innerHTML = '';
    document.querySelectorAll('.cat-btn').forEach(btn => {
        if (btn.dataset.cat === category) btn.classList.add('active');
        else btn.classList.remove('active');
    });
    loadStore(true);
}

function formatPriceWithEmojis(priceStr, currencyHint) {
    if (priceStr.includes('💎') || priceStr.includes('🪙')) return priceStr;
    const numbers = priceStr.match(/\d+/g);
    if (!numbers) return priceStr;
    if (currencyHint === 'diamond') return `💎 ${numbers[0]}`;
    if (currencyHint === 'gold') return `🪙 ${numbers[0]}`;
    if (numbers.length >= 2) return `💎 ${numbers[0]} / 🪙 ${numbers[1]}`;
    return `💎 ${numbers[0]}`;
}

function addItemCard(item) {
    const card = document.createElement('div');
    card.className = 'card';
    let currency = 'diamond';
    if (item.price_str.includes('🪙') && !item.price_str.includes('💎')) currency = 'gold';
    const displayPrice = formatPriceWithEmojis(item.price_str, currency);
    card.innerHTML = `
        <div class="sort-badge">#${item.sort_id}</div>
        <div class="card-img-container">
            <img class="card-img" src="/api/image/${item.item_id}" alt="item" onerror="this.src='https://via.placeholder.com/100?text=No+Image'">
        </div>
        <div class="price">${displayPrice}</div>
        <div class="expire">📅 ${item.expire_date}</div>
        <button class="btn-send" data-id="${item.commodity_id}" data-price="${item.price_str}" data-currency="${currency}">Send Gift</button>
    `;
    const sendBtn = card.querySelector('.btn-send');
    sendBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        let price = 0;
        const numbers = item.price_str.match(/\d+/g);
        if (numbers) price = parseInt(numbers[0]);
        selectedItem = {
            commodity_id: sendBtn.dataset.id,
            price: price,
            currency: sendBtn.dataset.currency
        };
        giftModal.style.display = 'flex';
    });
    itemsGrid.appendChild(card);
}

// Infinite scroll
window.addEventListener('scroll', () => {
    if (isLoading || !hasMore) return;
    if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 300) {
        loadStore(false);
    }
});

// Load button click: authenticate first then load store
loadBtn.addEventListener('click', async () => {
    loadBtn.disabled = true;
    loadBtn.innerText = 'Authenticating...';
    errorMsg.style.display = 'none';

    try {
        const jwt = await authenticate();
        currentJwt = jwt;
        currentCategory = 'All';
        currentPage = 1;
        allCategories = [];
        isLoading = false;
        hasMore = true;
        itemsGrid.innerHTML = '';
        await loadStore(true);
        loginBox.style.display = 'none';
        storeBox.style.display = 'block';
    } catch (err) {
        showError(err.message);
    } finally {
        loadBtn.disabled = false;
        loadBtn.innerText = 'LOAD GIFT STORE';
    }
});

// Send gift logic
confirmSendBtn.addEventListener('click', async () => {
    const uid = targetUid.value.trim();
    if (!uid) {
        alert('Please enter receiver UID');
        return;
    }
    if (!selectedItem) return;

    confirmSendBtn.disabled = true;
    confirmSendBtn.innerText = 'Sending...';
    try {
        const resp = await fetch('/api/send_gift', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jwt: currentJwt,
                receiver_uid: uid,
                commodity_id: selectedItem.commodity_id,
                price: selectedItem.price,
                currency: selectedItem.currency,
                message: giftMsg.value || 'Gift!'
            })
        });
        const data = await resp.json();
        if (data.success) {
            alert(data.message);
            closeModal();
            currentPage = 1;
            allCategories = [];
            itemsGrid.innerHTML = '';
            await loadStore(true);
        } else {
            alert('Error: ' + data.message);
        }
    } catch (err) {
        alert('Network error: ' + err.message);
    } finally {
        confirmSendBtn.disabled = false;
        confirmSendBtn.innerText = 'CONFIRM';
    }
});

function closeModal() {
    giftModal.style.display = 'none';
    targetUid.value = '';
    selectedItem = null;
}

window.onclick = function(event) {
    if (event.target === giftModal) closeModal();
};