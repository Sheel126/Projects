import api from './APIClient.js';

const category = document.querySelector('title').textContent;

const itemList = document.querySelector('#itemList');

const itemInput = document.querySelector('#itemForm');
const itemButton = itemInput.querySelector('button');
const itemName = itemInput.querySelector('#itemFormName');
const itemAmount = itemInput.querySelector('#itemFormAmount');

api.getAuthenticatedUser().then(user => {
    initializeAddItem(user.id);
    initializeItems();
});

function initializeAddItem(userId) {
    itemButton.addEventListener('click', () => {
        const name = itemName.value;
        const amount = itemAmount.value;

        if (name != '' && amount != '') {
            switch (category) {
                case 'Calories':
                    api.addCalorieItem(userId, name, amount).then(item => {
                        initalizeAddedItem(item);
                    });
                    break;
                case 'Water':
                    api.addWaterItem(userId, name, amount).then(item => {
                        initalizeAddedItem(item);
                    });
                    break;
                case 'Sleep':
                    api.addSleepItem(userId, name, amount).then(item => {
                        initalizeAddedItem(item);
                    });
                    break;
                case 'Steps':
                    api.addStepsItem(userId, name, amount).then(item => {
                        initalizeAddedItem(item);
                    });
                    break;
            }
        }
    });    
}

function initalizeAddedItem(item) {
    createItemHTML(item).then(itemElement => {
        itemList.prepend(itemElement);
        itemName.value = '';
        itemAmount.value = '';
    });
}

function initializeItems() {
    switch (category) {
        case 'Calories':
            api.getCalorieItems().then(items => {
                initializeItemsHelper(items);
            });
            break;
        case 'Water':
            api.getWaterItems().then(items => {
                initializeItemsHelper(items);
            });
            break;
        case 'Sleep':
            api.getSleepItems().then(items => {
                initializeItemsHelper(items);
            });
            break;
        case 'Steps':
            api.getStepsItems().then(items => {
                initializeItemsHelper(items);
            });
            break;
    }
}

function initializeItemsHelper(items) {
    const itemPromises = items.map(item => createItemHTML(item));
    
    Promise.all(itemPromises).then(itemElements => {
        itemElements.forEach(itemElement => {
            itemList.append(itemElement);
        });
    });
} 

function createItemHTML(item) {
    const itemTemplate = document.querySelector('#itemTemplate');
    const itemInstance = itemTemplate.content.cloneNode(true);
    const itemElement = itemInstance.querySelector('.itemContainer');

    const itemName = itemInstance.querySelector('.itemName');
    itemName.textContent = item.itemName;

    const itemAmount = itemInstance.querySelector('.itemAmount');
    itemAmount.textContent = item.amount;

    const itemDeleteButton = itemInstance.querySelector('.itemDeleteButton');
    itemDeleteButton.addEventListener('click', () => {
        switch (category) {
            case 'Calories':
                api.deleteCalorieItem(item.id).then(() => {
                    location.reload();
                });
                break;
            case 'Water':
                api.deleteWaterItem(item.id).then(() => {
                    location.reload();
                });
                break;
            case 'Sleep':
                api.deleteSleepItem(item.id).then(() => {
                    location.reload();
                });
                break;
            case 'Steps':
                api.deleteStepsItem(item.id).then(() => {
                    location.reload();
                });
                break;
        }
    });    

    return itemElement;
}