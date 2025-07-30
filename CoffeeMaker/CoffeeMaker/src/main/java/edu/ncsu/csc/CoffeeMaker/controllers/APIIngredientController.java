package edu.ncsu.csc.CoffeeMaker.controllers;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import edu.ncsu.csc.CoffeeMaker.models.Ingredient;
import edu.ncsu.csc.CoffeeMaker.models.enums.IngredientType;
import edu.ncsu.csc.CoffeeMaker.services.IngredientService;

/**
 * APIIngredientController maps API calls for Ingredients in the CoffeeMaker.
 */
@RestController
public class APIIngredientController extends APIController {

    /**
     * IngredientService object, to be autowired in by Spring to allow for
     * manipulating the ingredient model
     */
    @Autowired
    private IngredientService service;

    /**
     * REST API method to provide GET access to all ingredients in the system
     *
     * @return JSON representation of all ingredients
     */
    @GetMapping ( BASE_PATH + "/ingredients" )
    public List<Ingredient> getIngredients () {
        return service.findAll();
    }

    /**
     * REST API method to provide GET access to a specific ingredient, as
     * indicated by the path variable provided (the name of the ingredient
     * desired)
     *
     * @param type
     *            ingredient's type
     *
     * @return response to the request
     */
    @GetMapping ( BASE_PATH + "/ingredients/{type}" )
    public ResponseEntity<Ingredient> getIngredient ( @PathVariable final IngredientType type ) {
        final Ingredient ingredient = service.getIngredientsByType( type );
        return null == ingredient ? new ResponseEntity<Ingredient>( HttpStatus.NOT_FOUND )
                : new ResponseEntity<Ingredient>( ingredient, HttpStatus.OK );
    }

    /**
     * REST API method to provide POST access to the ingredient model. This is
     * used to create a new ingredient by automatically converting the JSON
     * RequestBody provided to a ingredient object. Invalid JSON will fail.
     *
     * @param ingredient
     *            The valid ingredient to be saved.
     * @return ResponseEntity indicating success if the ingredient could be
     *         saved to the inventory, or an error if it could not be
     */
    @PostMapping ( BASE_PATH + "/ingredients" )
    public ResponseEntity<Ingredient> createIngredient ( @RequestBody final Ingredient ingredient ) {
        // System.out.println( "INGREDIENT: " + ingredient.getId() );
        if ( null != service.getIngredientsByType( ingredient.getIngredient() ) ) {
            return new ResponseEntity<Ingredient>( HttpStatus.CONFLICT );
        }
        service.save( ingredient );
        return new ResponseEntity<Ingredient>( HttpStatus.OK );

    }

    /**
     * REST API method to provide PUT access to the ingredient model. This is
     * used to update an ingredient by automatically converting the JSON
     * RequestBody provided to a ingredient object. Invalid JSON will fail.
     *
     * @param ingredient
     *            the ingredient to update
     * @return ResponseEntity indicating success if the ingredient could bes
     *         saved to the inventory, or an error if it could not be
     */
    @PutMapping ( BASE_PATH + "/ingredients" )
    public ResponseEntity<Ingredient> updateIngredient ( @RequestBody final Ingredient ingredient ) {
        final Ingredient retrivedIngredient = service.getIngredientsByType( ingredient.getIngredient() );
        if ( retrivedIngredient == null ) {
            return new ResponseEntity<Ingredient>( HttpStatus.NOT_FOUND );
        }
        retrivedIngredient.setAmount( ingredient.getAmount() );
        service.save( retrivedIngredient );
        return new ResponseEntity<Ingredient>( HttpStatus.OK );
    }

    /**
     * REST API method to allow deleting a ingredient from the CoffeeMaker's
     * Inventory, by making a DELETE request to the API endpoint and indicating
     * the ingredient to delete (as a path variable)
     *
     * @param type
     *            the ingredient type
     *
     * @return Success if the ingredient could be deleted; an error if the
     *         ingredient does not exist
     */
    @DeleteMapping ( BASE_PATH + "/ingredients/{type}" )
    public ResponseEntity<Ingredient> deleteIngredient ( @PathVariable final IngredientType type ) {
        final Ingredient ingredient = service.getIngredientsByType( type );
        if ( null == ingredient ) {
            return new ResponseEntity<Ingredient>( HttpStatus.NOT_FOUND );
        }
        service.delete( ingredient );

        return new ResponseEntity<Ingredient>( ingredient, HttpStatus.OK );
    }

}
