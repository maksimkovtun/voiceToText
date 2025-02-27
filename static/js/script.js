var loginModal = document.getElementById('login-modal');
var registerModal = document.getElementById('register-modal');

var loginButton = document.getElementById('login-button');
var closeButton = document.querySelector('.close');
var loginLink = document.getElementById('login-link');
var registerLink = document.getElementById('register-link');

var resultsLink = document.getElementById('results-link');
var addTestLink = document.getElementById('add-test-link');

var registerLink = document.getElementById('register-link');

function showResultsLink() {
    resultsLink.style.display = 'block';
}

function showAddTestLink() {
    addTestLink.style.display = 'block';
}

function openLoginModal() {
    loginModal.style.display = 'block';
    registerModal.style.display = 'none';
}

function openRegisterModal() {
    loginModal.style.display = 'none';
    registerModal.style.display = 'block';
}

loginButton.addEventListener('click', openLoginModal);
closeButton.addEventListener('click', function() {
    loginModal.style.display = 'none';
    registerModal.style.display = 'none';
});
loginLink.addEventListener('click', openLoginModal);
registerLink.addEventListener('click', openRegisterModal);

var registerLink = document.getElementById('register-link');

registerLink.addEventListener('click', function() {
    document.getElementById('register-modal').style.display = 'block';
    document.getElementById('login-modal').style.display = 'none';
});

if (isAuthenticated) {
    document.getElementById('login-button').textContent = 'Logout';
} else {
    document.getElementById('login-button').textContent = 'Auth';
}





