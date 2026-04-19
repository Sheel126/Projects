import { describe, test } from 'vitest';
import { render, screen } from '@testing-library/react'
import { http, HttpRespones } from 'msw'
import { setupServer } from 'msw/node'
import Home from '../pages/Home.jsx';
import Login from '../pages/Login.jsx';
import Register from '../pages/Register.jsx'

const server = setupServer(
  http.get('/greeting', () => {
    return HttpResponse.json({greeting: 'hello there'})
  }),
)

describe('A truthy statement', () => {
  test('should be equal to 2', () => {
    expect(1+1).toEqual(2);
  })
})

describe('Home', () => {
  test('renders the App component', () => {
    render(<Home />)
    
    screen.debug(); // prints out the jsx in the App component unto the command line
  })
})

describe('API Test', () => {
  test('handle server error', async() => {
    server.use(
      http.post('http://localhost:8001/api/login/', (req, res, ctx) => {
        return new HttpResponse(null, {status: 500})
      })
    )
    render(<Register />)
    
  })
})