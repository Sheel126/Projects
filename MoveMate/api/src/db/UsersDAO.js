const db = require('./DBConnection');
const User = require('./models/user');
const crypto = require('crypto');

module.exports = {
    getUserByCredentials: (username, password) => {
        return db.query('SELECT * FROM user WHERE usr_username=?', [username]).then(rows => {
            if (rows.length === 1) { 
                const user = new User(rows[0]);
                return user.validatePassword(password);
            }
            throw new Error("No such user");
        });

    },

    postUser: (username, password) => {
        return new Promise((resolve, reject) => {
            const salt = crypto.randomBytes(32).toString('hex');
            const passwordHash = crypto
                .pbkdf2Sync(password, salt, 100000, 64, 'sha512')
                .toString('hex');

            db.query('SELECT * FROM user WHERE usr_username=?', [username]).then(rows => {
                if (rows.length > 0) {
                    reject({ message: "User already exists", code: 409 });
                    return;
                }

                db.query('INSERT INTO user (usr_username, usr_password, usr_salt) VALUES (?, ?, ?) RETURNING *',
                    [username, passwordHash, salt]
                ).then(resultRows => {
                    if (resultRows[0]) {
                        resolve(new User(resultRows[0]));
                    } else {
                        reject({ message: "Failed to create user", code: 500 });
                    }
                });
            });
        });
    }
}