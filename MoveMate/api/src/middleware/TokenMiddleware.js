const jwt = require('jsonwebtoken');
const API_SECRET = process.env.MOVEMATE_SECRET_KEY

const TOKEN_COOKIE_NAME = "MoveMateToken";

exports.TokenMiddleware = (req, res, next) => {

    let token = null;
    if (req.cookies[TOKEN_COOKIE_NAME]) { 
        token = req.cookies[TOKEN_COOKIE_NAME];
    } else { 
        const authHeader = req.get('Authorization');
        if (authHeader && authHeader.startsWith("Bearer ")) {
            token = authHeader.split(" ")[1].trim();
        }
    }

    if (token == null) {
        res.status(401).json({ error: 'Not Authenticated' });
    } else {
        try {
            const payload = jwt.verify(token, API_SECRET);
            req.user = payload.user;
            next();
        } catch (error) {
            res.status(401).json({ error: 'Not Authenticated' });
        }
    }
}


exports.generateToken = (req, res, user) => {
    const payload = {
        "exp": Math.floor(Date.now() / 1000) + (60 * 60),
        "user": user
    }

    const token = jwt.sign(payload, API_SECRET);

    res.cookie(TOKEN_COOKIE_NAME, token, { maxAge: 60 * 60 * 1000, httpOnly: true, secure: true });
};


exports.removeToken = (req, res) => {
    res.cookie(TOKEN_COOKIE_NAME, '', { maxAge: -1000, httpOnly: true, secure: true })
};
