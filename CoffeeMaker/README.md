# CoffeeMaker


*Line Coverage (should be >=70%)*

![Coverage](.github/badges/jacoco.svg)

*Branch Coverage (should be >=50%)*

![Branches](.github/badges/branches.svg)

## addIngredient:
post: /api/v1/ingredients
post message body: [{ingredient: 'MILK', amount: 10, $$hashKey: 'object:3'}]  
return: Status 200


put: /api/v1/inventory 
put message body: [{ingredient: 'SUGAR', amount: 5, $$hashKey: 'object:3'}]  
return: Status 200


get: /api/v1/inventory 
return: [{id:32, ingredients: Array(1)}]


## addRecipe:
post: /api/v1/recipes 
post message body: {name: 'Sweetened Milk', price: 10, ingredients: Array(2)}
return: Status 200

