module.exports = class Steps {
    id = null;
    userId = null;
    itemName = null;
    amount = null;

    constructor(data) {
        this.id = data.stt_id;
        this.userId = data.stt_usr_id;
        this.itemName = data.stt_item;
        this.amount = data.stt_steps;
        this.date = data.stt_date;
    }
}