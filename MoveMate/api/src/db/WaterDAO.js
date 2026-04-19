const db = require('./DBConnection');

const Water = require('./models/water');

module.exports = {
    getWater: (id) => {
        return db.query('SELECT * FROM water_tracking WHERE wt_usr_id=? ORDER BY wt_date DESC', [id]).then(rows => {
            let currentWater = null;
            const waterCounts = [];
            rows.forEach(water => {
                currentWater = new Water(water);
                waterCounts.push(currentWater);
            });

            return waterCounts;
        });
    },

    getWaterAmount(id) {
        return db.query('SELECT SUM(wt_water) AS totalWater FROM water_tracking WHERE wt_usr_id = ?', [id])
            .then(result => {
                if (result.length > 0) {
                    return result[0].totalWater || 0;
                }
                return 0;
            });
    },

    postWater: (waterData) => {
        return db.query('INSERT INTO water_tracking (wt_usr_id, wt_item, wt_water, wt_date) VALUES (?, ?, ?, ?)', 
            [waterData.userId, waterData.itemName, waterData.water, new Date()]
        ).then(result => {
            return 'Posted';
        });
    },

    deleteWater(wtId) {
        return db.query('DELETE FROM water_tracking WHERE wt_id = ?', [wtId]).then(result => {
            console.log('Water entry deleted successfully.');
            resolve(true);
        });
    }
}