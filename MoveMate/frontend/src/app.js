const express = require('express');
const cookieParser = require('cookie-parser');
const path = require('path');

const app = express();
const router = express.Router();

router.use(cookieParser());
const { isAuthenticated } = require('./middleware/TokenMiddleware');

const PORT = process.env.PORT;

router.use(express.static(__dirname + '/static'));

const templatesPath = path.join(__dirname, 'templates');

router.get('/', (req, res) => {
    if (isAuthenticated(req, res)) {
        res.sendFile(path.join(templatesPath, 'home.html'));
    } else {
        res.sendFile(path.join(templatesPath, 'splash.html'));
    }
});

router.get('/recommendations', (req, res) => {
    res.sendFile(path.join(templatesPath, 'recommendations.html'));
});

router.get('/reminders', (req, res) => {
    res.sendFile(path.join(templatesPath, 'reminders.html'));
});

router.get('/calories', (req, res) => {
    res.sendFile(path.join(templatesPath, 'calories.html'));
});

router.get('/water', (req, res) => {
    res.sendFile(path.join(templatesPath, 'water.html'));
});

router.get('/sleep', (req, res) => {
    res.sendFile(path.join(templatesPath, 'sleep.html'));
});

router.get('/steps', (req, res) => {
    res.sendFile(path.join(templatesPath, 'steps.html'));
});

router.get('/login', (req, res) => {
    res.sendFile(path.join(templatesPath, 'login.html'));
});

router.get('/register', (req, res) => {
    res.sendFile(path.join(templatesPath, 'register.html'));
});

router.get('/offline', (req, res) => {
    res.sendFile(path.join(templatesPath, 'offline.html'));
});

app.use(router);

app.listen(PORT, () => console.log(`Server listening on port: ${PORT}`));