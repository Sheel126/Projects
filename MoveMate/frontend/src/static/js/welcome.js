import api from "./APIClient.js";

document.addEventListener('DOMContentLoaded', () => {
    api.getGoals().catch((err) => {
        if (err.status === 404) {
            init();
        }
    })
});

function formatNumberWithCommas(number) {
    if (!number) return "";
    return new Intl.NumberFormat('en-US').format(number);
}

function handleSubmit() {
    const numberFields = document.querySelectorAll('#welcomePopup input');

    numberFields.forEach((f) => {
        api.editGoal(f.id, f.value.replace(/[^0-9]/g, ''))
    });

    closePopup();

    setTimeout(() => {
        document.location = "./";
    }, 500);
}

function closePopup() {
    document.getElementById('welcomePopup').style.opacity = 0;
    document.querySelector('header').classList.remove("blur");
    document.querySelector('main').classList.remove("blur");
}

function init() {
    const numberFields = document.querySelectorAll('#welcomePopup input');

    numberFields.forEach(field => {
        field.addEventListener('input', (e) => {
            let rawValue = e.target.value.replace(/,/g, '');
            rawValue = rawValue.replace(/[^0-9]/g, '');
            e.target.value = formatNumberWithCommas(rawValue);
        });

        field.addEventListener('blur', (e) => {
            let rawValue = e.target.value.replace(/,/g, '');
            e.target.value = formatNumberWithCommas(rawValue);
        });

        field.addEventListener('keypress', (e) => {
            const char = String.fromCharCode(e.which);
            if (!/[0-9]/.test(char)) {
                e.preventDefault();
            }
        });
    });

    let btn = document.querySelector("#welcomeSubmit");
    btn.addEventListener("click", handleSubmit);

    document.getElementById('welcomePopup').style.opacity = 1;
    document.querySelector('header').classList.add("blur");
    document.querySelector('main').classList.add("blur");
}