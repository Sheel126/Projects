function registerServiceWorker() {
    if (!navigator.serviceWorker) {
        return;
    }

    navigator.serviceWorker.register('/serviceWorker.js')
        .then(registration => {
            if (!navigator.serviceWorker.controller) {
                return;
            }

            if (registration.installing) {
                console.log('Service worker installing');
            } else if (registration.waiting) {
                console.log('Service worker installed, but waiting');
                newServiceWorkerReady(registration.waiting);
            } else if (registration.active) {
                console.log('Service worker active');
            }

            registration.addEventListener('updatefound', () => {
                console.log("SW update found", registration, navigator.serviceWorker.controller);
                newServiceWorkerReady(registration.installing);
            });
        })
        .catch(error => {
            console.error(`Registration failed with error: ${error}`);
        });

    navigator.serviceWorker.addEventListener('message', event => {
        console.log('SW message', event.data);
    });

    let refreshing = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (refreshing) return;
        window.location.reload();
        refreshing = true;
    });
};

function newServiceWorkerReady(worker) {
    const popup = document.createElement('div');
    popup.className = "popup";
    popup.innerHTML = '<div>New Version Available</div>';

    const buttonOk = document.createElement('button');
    buttonOk.innerHTML = 'Update';
    buttonOk.addEventListener('click', e => {
        worker.postMessage({ action: 'skipWaiting' });
    });
    popup.appendChild(buttonOk);

    const buttonCancel = document.createElement('button');
    buttonCancel.innerHTML = 'Dismiss';
    buttonCancel.addEventListener('click', e => {
        document.body.removeChild(popup);
    });
    popup.appendChild(buttonCancel);

    document.body.appendChild(popup);
}

registerServiceWorker();