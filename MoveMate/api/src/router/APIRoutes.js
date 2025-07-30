const express = require('express');
const router = express.Router();
const cookieParser = require('cookie-parser');

router.use(cookieParser());
router.use(express.json());

const { generateToken, removeToken, TokenMiddleware } = require('../middleware/TokenMiddleware');

const CaloriesDAO = require('../db/CaloriesDAO');
const RemindersDAO = require('../db/RemindersDAO');
const StepsDAO = require('../db/StepsDAO');
const SleepDAO = require('../db/SleepDAO');
const WaterDAO = require('../db/WaterDAO');
const GoalsDAO = require('../db/GoalsDAO');
const StreaksDAO = require('../db/StreaksDAO');
const UserDAO = require('../db/UsersDAO');
const RecommendationsDAO = require('../db/RecommendationsDAO');

// Authentication

router.post('/register', (req, res) => {
    const { username, password } = req.body;
    if (username && password) {
        UserDAO.postUser(username, password).then(user => {
            generateToken(req, res, user);
            res.json(user);
        }).catch(err => {
            res.status(err.code || 500).json({ error: err.message || "Internal server error." });
        });
    } else {
        res.status(400).json({ error: 'Credentials not provided' });
    }
});

router.post('/login', (req, res) => {
    const { username, password } = req.body;
    if (username && password) {
        UserDAO.getUserByCredentials(username, password).then(user => {
            generateToken(req, res, user);

            res.json({ user: user });
        }).catch(err => {
            res.status(err.code || 500).json({ error: err.message });
        });
    } else {
        res.status(400).json({ error: 'Credentials not provided' });
    }
});

router.post('/logout', (req, res) => {
    removeToken(req, res);
    res.json({ success: true });
});

router.get('/users/current', TokenMiddleware, (req, res) => {
    res.json(req.user);
});

// Calories

router.get('/calories', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    CaloriesDAO.getCaloriesUserId(id).then(calories => {
        res.json(calories);
    }).catch(err => {
        res.status(500).json({ error: 'Internal Server Error' });
    });
});

router.get('/calories/amount', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    CaloriesDAO.getCalorieAmount(id).then(amount => {
        res.json(amount);
    }).catch(err => {
        res.status(500).json({ error: 'Internal Server Error' });
    });
});

router.post('/calories', TokenMiddleware, (req, res) => {
    const calorieData = {
        userId: req.user.id,
        itemName: req.body.name,
        calories: req.body.amount,
    }

    CaloriesDAO.postCalories(calorieData).then(calorie => {
        res.json(calorie);
    }).catch(err => {
        res.status(500).json({ error: 'Internal server error' });
    });
});

router.delete('/calories/:calorieId', TokenMiddleware, (req, res) => {
    const calorieId = parseInt(req.params.calorieId);

    CaloriesDAO.deleteCalories(calorieId).then(() => {
        res.json({message: "Success"});
    }).catch(err => {
        res.status(500).json({ error: 'Internal server error' });
    });
});

router.get('/water', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    WaterDAO.getWater(id).then(water => {
        res.json(water);
    }).catch(err => {
        res.status(500).json({ error: 'Internal Server Error' });
    });
});

// Water

router.get('/water/amount', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    WaterDAO.getWaterAmount(id).then(amount => {
        res.json(amount);
    }).catch(err => {
        res.status(500).json({ error: 'Internal Server Error' });
    });
});

router.post('/water', TokenMiddleware, (req, res) => {
    const waterData = {
        userId: req.user.id,
        itemName: req.body.name,
        water: req.body.amount,
    }

    WaterDAO.postWater(waterData).then(water => {
        res.json(water);
    }).catch(err => {
        res.status(500).json({ error: 'Internal server error' });
    });
});

router.delete('/water/:waterId', TokenMiddleware, (req, res) => {
    const waterId = parseInt(req.params.waterId);

    WaterDAO.deleteWater(waterId).then(() => {
        res.json({message: "Success"});
    }).catch(err => {
        res.status(500).json({ error: 'Internal server error' });
    });
});





// Sleep

router.get('/sleep', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    SleepDAO.getSleep(id).then(sleep => {
        res.json(sleep);
    }).catch(err => {
        res.status(500).json({ error: 'Internal Server Error' });
    });
});

router.get('/sleep/amount', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    SleepDAO.getSleepAmount(id).then(amount => {
        res.json(amount);
    }).catch(err => {
        res.status(500).json({ error: 'Internal Server Error' });
    });
});

router.post('/sleep', TokenMiddleware, (req, res) => {
    const sleepData = {
        userId: req.user.id,
        itemName: req.body.name,
        sleep: req.body.amount,
    }

    SleepDAO.postSleep(sleepData).then(sleep => {
        res.json(sleep);
    }).catch(err => {
        res.status(500).json({ error: 'Internal server error' });
    });
});

router.delete('/sleep/:sleepId', TokenMiddleware, (req, res) => {
    const sleepId = parseInt(req.params.sleepId);

    SleepDAO.deleteSleep(sleepId).then(() => {
        res.json({message: "Success"});
    }).catch(err => {
        res.status(500).json({ error: 'Internal server error' });
    });
});





// Steps

router.get('/steps', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    StepsDAO.getSteps(id).then(steps => {
        res.json(steps);
    }).catch(err => {
        res.status(500).json({ error: 'Internal Server Error' });
    });
});

router.get('/steps/amount', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    StepsDAO.getStepsAmount(id).then(amount => {
        res.json(amount);
    }).catch(err => {
        res.status(500).json({ error: 'Internal Server Error' });
    });
});

router.post('/steps', TokenMiddleware, (req, res) => {
    const stepsData = {
        userId: req.user.id,
        itemName: req.body.name,
        steps: req.body.amount,
    }

    StepsDAO.postSteps(stepsData).then(steps => {
        res.json(steps);
    }).catch(err => {
        res.status(500).json({ error: 'Internal server error' });
    });
});

router.delete('/steps/:stepsId', TokenMiddleware, (req, res) => {
    const stepsId = parseInt(req.params.stepsId);

    StepsDAO.deleteSteps(stepsId).then(() => {
        res.json({message: "Success"});
    }).catch(err => {
        res.status(500).json({ error: 'Internal server error' });
    });
});





// Reminders

router.get('/reminders', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    RemindersDAO.getReminders(id).then(reminders => {
        res.json(reminders);
    }).catch(err => {
        res.status(500).json({ error: "Internal Server Error" });
    });
});

router.post('/reminders', TokenMiddleware, (req, res) => {
    let newReminder = req.body;
    RemindersDAO.postReminders(newReminder).then(reminder => {
        res.json(reminder);
    })
        .catch(err => {
            res.status(500).json({ error: 'Internal server error' });
        });
});

router.put('/reminders', TokenMiddleware, (req, res) => {
    let updatedReminder = req.body;
    RemindersDAO.updateCompleted(updatedReminder).then(reminder => {
        res.json(reminder);
    }).catch(err => {
        res.status(500).json({error: 'Internal server error'});
    });
});





// Goals

/**
 * Retrieves a list of goals for the user
 */
router.get('/goals', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    GoalsDAO.getGoals(id).then(goals => {
        res.status(200).json(goals);
    }).catch(err => {
        res.status(err.code || 500).json({ error: err.message || "Internal server error." });
    });
});

/**
 * Adds or updates a goal for a given category. If a goal exists under a category it will
 * be updated to the new target
 */
router.post('/goals', TokenMiddleware, (req, res) => {
    const goalData = {
        userId: req.user.id,
        category: req.body.category,
        target: req.body.target,
    };

    GoalsDAO.postPutGoal(goalData).then(result => {
        res.status(result.code || 200).json(result);
    }).catch(err => {
        res.status(err.code || 500).json({ error: err.message || "Internal server error." });
    });
});



// Streaks
router.get('/streaks', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    StreaksDAO.calculateStreaks(id).then(streaks => {
        res.json(streaks);
    }).catch(err => {
        console.log(err);
        res.status(500).json({ error: 'Internal server error' });
    });
});

router.post('/streaks', TokenMiddleware, (req, res) => {
    const newStreak = req.body;
    StreaksDAO.postStreaks(newStreak).then(streaks => {
        res.json(streaks);
    });
});

router.get('/sleep', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    SleepDAO.getSleep(id).then(sleep => {
        res.json(sleep);
    }).catch(err => {
        res.status(500).json({ error: 'Internal server error' });
    });
});

router.post('/sleep', TokenMiddleware, (req, res) => {
    let newSleep = req.body;
    SleepDAO.postSleep(newSleep).then(sleep => {
        res.json(sleep);
    });
});

router.get('/water', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    WaterDAO.getWater(id).then(water => {
        res.json(water);
    }).catch(err => {
        res.status(500).json({ error: 'Internal server error' });
    });
});

router.post('/water', TokenMiddleware, (req, res) => {
    const newWaterAccount = req.body;
    WaterDAO.postWater(newWaterAccount).then(water => {
        res.json(water);
    });
});

router.post('/userGoals', TokenMiddleware, async (req, res) => {
    const newUserGoal = req.body;

    const gptResponse = await RecommendationsDAO.getRecommendations(newUserGoal.title);
    newUserGoal.recommendations = gptResponse;
    RecommendationsDAO.postUserGoals(newUserGoal).then(goal => {
        res.json(goal);
    });
});

router.get('/userGoals', TokenMiddleware, (req, res) => {
    const id = req.user.id;
    RecommendationsDAO.getUserGoals(id).then(goals => {
        res.json(goals);
    }).catch(err => {
        res.status(500).json({ error: 'Internal server error' });
    })
});

module.exports = router;