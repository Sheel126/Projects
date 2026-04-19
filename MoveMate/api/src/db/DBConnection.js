const mariadb = require('mariadb');

let pool;

exports.getDatabsaeConnection = () => {
    if (!pool) {
        pool = mariadb.createPool({
            host: process.env.DB_HOST,
            port: process.env.DB_PORT,
            user: process.env.MYSQL_USER,
            password: process.env.MYSQL_PASSWORD,
            database: process.env.MYSQL_DATABASE,
            charset: process.env.DB_CHARSET
        });
    }
    return pool;
}

exports.query = (query, params = []) => {
    const pool = exports.getDatabsaeConnection();
    return pool.query(query, params).catch(err => {
        console.error(err);
        throw err;
    });
}

exports.close = () => {
    if (pool !== null) {
        pool.end();
        pool = null;
    }
}