const STATIC_CACHE_NAME = "movemate-static-v1";

function log(...data) {
    console.log("SWv1.0", ...data);
}

log("SW Script executing - adding event listeners");

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(STATIC_CACHE_NAME).then(cache => {
            return cache.addAll([
                '/offline',
                '/css/auth.css',
                '/css/category.css',
                '/css/home.css',
                '/css/recommendations.css',
                '/css/reminders.css',
                '/css/splash.css',
                '/css/styles.css',
                '/css/welcomePopup.css',
                '/js/APIClient.js',
                '/js/auth.js',
                '/js/common.js',
                '/js/category.js',
                '/js/HTTPClient.js',
                '/js/login.js',
                '/js/goal.js',
                '/js/recommendations.js',
                '/js/register.js',
                '/js/reminders.js',
                '/js/welcome.js',
                'https://unpkg.com/leaflet@1.9.1/dist/leaflet.css',
                'https://unpkg.com/leaflet@1.9.1/dist/leaflet.js',
                'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css',
                'https://fonts.googleapis.com/css2?family=Kanit:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&display=swap'
            ]);
        })
    );
    log('install', event);
    // As soon as this method returns, the service worker is considered installed
});

self.addEventListener('activate', event => {
    log('activate', event);

    // As soon as this method returns, the service worker is considered active
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return cacheNames.filter(cacheName => cacheName.startsWith('movemate-') && cacheName != STATIC_CACHE_NAME)
        }).then(oldCaches => {
            return Promise.all(
                oldCaches.map(cacheName => {
                    return caches.delete(cacheName);
                })
            );
        })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        networkFirst(event.request)
    );

});


function fetchAndCache(request) {
    return fetch(request).then(response => {
        var requestUrl = new URL(request.url);
        //Cache successful GET requests that are not browser extensions
        if (response.ok && request.method === "GET" && !requestUrl.protocol.startsWith('chrome-extension')) {
            caches.open(STATIC_CACHE_NAME).then((cache) => {
                cache.put(request, response);
            });
        }
        return response.clone();
    });
}

function cacheFirst(request) {
    return caches.match(request)
        .then(response => {
            //Return a response if we have one cached. Otherwise, get from the network
            return response || fetchAndCache(request);
        })
        .catch(error => {
            // This will only be called if there is an error fetching from the network
            return caches.match('/offline');
        });
}

function networkFirst(request) {
    return fetchAndCache(request)
        .catch(error => {
            //If we get an error, try to return from cache
            return caches.match(request);
        })
        .then(response => {
            return response || caches.match('/offline');
        });
}

self.addEventListener('message', event => {
    log('message', event.data);
    if (event.data.action === 'skipWaiting') {
        self.skipWaiting();
    }
});