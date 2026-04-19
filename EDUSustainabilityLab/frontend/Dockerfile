# Use official Node.js image
FROM node:18-alpine

# Set working directory inside the container
WORKDIR /app

# Copy package.json and install dependencies
COPY package.json ./
COPY package-lock.json ./
RUN npm install
RUN npm install --save-dev vitest
RUN npm install --save-dev jsdom
RUN npm install --save-dev @testing-library/jest-dom @testing-library/react @testing-library/user-event
#RUN npm i -D @vitest/coverage-istanbul@2.1.8
RUN npm install msw@latest --save-dev
RUN npm install chart.js react-chartjs-2
RUN npm install dotenv
RUN npm install dotenv-expand
RUN npm install axios
RUN npm install recharts


# Copy the rest of the code into the container
COPY . .

# Build the React app for production
RUN npm run build

# Install a lightweight static file server to serve the React app
RUN npm install -g serve

# Serve the build folder on port 3000
CMD ["serve", "-s", "dist"]

# Expose port 3000 for React app
EXPOSE 3000
