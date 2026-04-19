const db = require('./DBConnection');
const Recommendations = require('./models/recommendations');

module.exports = {

    getUserGoals: (id) => {
        return db.query('SELECT * FROM user_goals WHERE usr_id=?', [id])
        .then(rows => {
            let currentGoal = null;
            const goals = [];

            rows.forEach(goal => {
                currentGoal = new Recommendations(goal);
                goals.push(currentGoal);
            });

            return goals;
        });
    },

    postUserGoals: (data) => {
        return db.query('INSERT INTO user_goals (usr_id, user_goal_title, user_goal_completed, user_goal_recommendation) VALUES (?, ?, ?, ?)', 
            [data.userId, data.title, data.completed, data.recommendations]
        ).then((result) => {
            return 'Posted';
        });
    },

    getRecommendations: async (goal) => {
        console.log(goal);
        try {
            const response = await fetch('https://api.openai.com/v1/chat/completions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: // Token here,
                },
                body: JSON.stringify({
                    model: 'gpt-3.5-turbo',
                    messages: [
                        { role: 'system', content: 'You are a helpful assistant.' },
                        { role: 'user', content: `Goal: ${goal}. Suggestions? not a list and 100 tokens` },
                    ],
                    max_tokens: 100,
                }),
            });
            console.log("RESPONSE: ", response);
            const data = await response.json();
            return data.choices[0].message.content;
        } catch (error) {
            console.error('Error:', error.message);
        }
    }
}