const jwt = require('jsonwebtoken');
const API_SECRET = process.env.MOVEMATE_SECRET_KEY

const TOKEN_COOKIE_NAME = "MoveMateToken";

exports.isAuthenticated = (req, res) => {
    let token;

    if (req.cookies[TOKEN_COOKIE_NAME]) { 
        token = req.cookies[TOKEN_COOKIE_NAME]; 

    } else {
        const authHeader = req.get('Authorization');
        if (authHeader && authHeader.startsWith("Bearer ")) {
            token = authHeader.split(" ")[1].trim();
        }
    }

    console.log("token:", token);

    if (!token) {
        console.log("returned false");
        return false;
    }

    try {
        const payload = jwt.verify(token, API_SECRET);
        console.log(payload);
        req.user = payload.user;

        return true;
    } catch (error) {
        console.log(error);
        return false;
    }
}

exports.TokenMiddleware = (req, res, next) => {
    if (module.exports.isAuthenticated(req, res)) {
        next();
    } else {
        res.status(401).json({ error: 'Not Authenticated' });
    }
}