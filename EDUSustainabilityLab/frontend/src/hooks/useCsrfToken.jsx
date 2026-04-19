import { useState, useEffect } from 'react';

export function useCsrfToken(name = 'csrftoken') {
  const [csrfToken, setCsrfToken] = useState(null);

  useEffect(() => {
    function getCookie(name) {
      let cookieValue = null;
      if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let i = 0; i < cookies.length; i++) {
          const cookie = cookies[i].trim();
          if (cookie.startsWith(name + "=")) {
            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            break;
          }
        }
      }
      return cookieValue;
    }

    // Retrieve and set the CSRF token
    setCsrfToken(getCookie(name));
  }, [name]);

  return csrfToken;
}
