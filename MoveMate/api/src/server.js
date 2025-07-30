const express = require('express');

const app = express();
const PORT = process.env.PORT;

app.use(express.json());

const routes = require('./router/routes');
app.use(routes);

app.listen(PORT, () => console.log(`Server listening on port: ${PORT}`));