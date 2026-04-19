const express = require('express');
const router = express.Router();

const APIRoutes = require('./APIRoutes');

router.use(APIRoutes);

module.exports = router;