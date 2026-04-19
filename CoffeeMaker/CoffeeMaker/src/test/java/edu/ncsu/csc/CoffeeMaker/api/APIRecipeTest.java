package edu.ncsu.csc.CoffeeMaker.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import javax.transaction.Transactional;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.junit.jupiter.SpringExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import edu.ncsu.csc.CoffeeMaker.common.TestUtils;
import edu.ncsu.csc.CoffeeMaker.models.Ingredient;
import edu.ncsu.csc.CoffeeMaker.models.Recipe;
import edu.ncsu.csc.CoffeeMaker.models.enums.IngredientType;
import edu.ncsu.csc.CoffeeMaker.services.RecipeService;

@SpringBootTest
@AutoConfigureMockMvc
@ExtendWith ( SpringExtension.class )
public class APIRecipeTest {

    /**
     * MockMvc uses Spring's testing framework to handle requests to the REST
     * API
     */
    private MockMvc               mvc;

    @Autowired
    private WebApplicationContext context;

    @Autowired
    private RecipeService         service;

    /**
     * Sets up the tests.
     */
    @BeforeEach
    public void setup () {
        mvc = MockMvcBuilders.webAppContextSetup( context ).build();

        service.deleteAll();
    }

    @Test
    @Transactional
    public void ensureRecipe () throws Exception {
        service.deleteAll();

        final Recipe r = new Recipe();
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 5 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 3 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 4 );
        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 8 );
        r.addIngredient( coffee );
        r.addIngredient( sugar );
        r.addIngredient( milk );
        r.addIngredient( chocolate );
        r.setPrice( 10 );
        r.setName( "Mocha" );

        mvc.perform( post( "/api/v1/recipes" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( r ) ) ).andExpect( status().isOk() );

    }

    @Test
    @Transactional
    public void testRecipeAPI () throws Exception {

        service.deleteAll();

        final Recipe recipe = new Recipe();
        recipe.setName( "Delicious Not-Coffee" );
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 10 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 20 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 5 );
        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 1 );
        recipe.addIngredient( coffee );
        recipe.addIngredient( sugar );
        recipe.addIngredient( milk );
        recipe.addIngredient( chocolate );

        recipe.setPrice( 5 );

        mvc.perform( post( "/api/v1/recipes" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( recipe ) ) );

        Assertions.assertEquals( 1, (int) service.count() );

    }

    @Test
    @Transactional
    public void testAddRecipe2 () throws Exception {

        /* Tests a recipe with a duplicate name to make sure it's rejected */

        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );
        final String name = "Coffee";
        final Recipe r1 = createRecipe( name, 50, 3, 1, 1, 0 );

        service.save( r1 );

        final Recipe r2 = createRecipe( name, 50, 3, 1, 1, 0 );
        mvc.perform( post( "/api/v1/recipes" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( r2 ) ) ).andExpect( status().is4xxClientError() );

        Assertions.assertEquals( 1, service.findAll().size(), "There should only one recipe in the CoffeeMaker" );
    }

    @Test
    @Transactional
    public void testAddRecipe15 () throws Exception {

        /* Tests to make sure that our cap of 3 recipes is enforced */

        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );

        final Recipe r1 = createRecipe( "Coffee", 50, 3, 1, 1, 0 );
        service.save( r1 );
        final Recipe r2 = createRecipe( "Mocha", 50, 3, 1, 1, 2 );
        service.save( r2 );
        final Recipe r3 = createRecipe( "Latte", 60, 3, 2, 2, 0 );
        service.save( r3 );

        Assertions.assertEquals( 3, service.count(),
                "Creating three recipes should result in three recipes in the database" );

        final Recipe r4 = createRecipe( "Hot Chocolate", 75, 0, 2, 1, 2 );

        mvc.perform( post( "/api/v1/recipes" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( r4 ) ) ).andExpect( status().isInsufficientStorage() );

        Assertions.assertEquals( 3, service.count(), "Creating a fourth recipe should not get saved" );
    }

    @Test
    @Transactional
    public void testDeleteRecipe4 () throws Exception {

        /* Tests to make sure that our cap of 3 recipes is enforced */
        service.deleteAll();

        final Recipe recipe = new Recipe();
        recipe.setName( "Delicious Not-Coffee" );
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 10 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 20 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 5 );
        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 1 );
        recipe.addIngredient( coffee );
        recipe.addIngredient( sugar );
        recipe.addIngredient( milk );
        recipe.addIngredient( chocolate );

        recipe.setPrice( 5 );

        mvc.perform( post( "/api/v1/recipes" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( recipe ) ) );

        Assertions.assertEquals( 1, (int) service.count() );

        mvc.perform( delete( "/api/v1/recipes/Delicious Not-Coffee" ) ).andExpect( status().isOk() );

        Assertions.assertEquals( 0, (int) service.count() );
    }

    @Test
    public void testGetRecipeError () throws Exception {
        mvc.perform( get( "/api/v1/recipes/{name}", "NonExistentRecipe" ) ).andExpect( status().isNotFound() ); // status
    }

    private Recipe createRecipe ( final String name, final Integer price, final Integer coffee, final Integer milk,
            final Integer sugar, final Integer chocolate ) {
        final Recipe recipe = new Recipe();
        recipe.setName( name );
        recipe.setPrice( price );
        final Ingredient coffee1 = new Ingredient( IngredientType.COFFEE, 3 );
        final Ingredient sugar1 = new Ingredient( IngredientType.SUGAR, 1 );
        final Ingredient milk1 = new Ingredient( IngredientType.MILK, 1 );
        final Ingredient chocolate1 = new Ingredient( IngredientType.CHOCOLATE, 0 );
        recipe.addIngredient( coffee1 );
        recipe.addIngredient( sugar1 );
        recipe.addIngredient( milk1 );
        recipe.addIngredient( chocolate1 );

        return recipe;
    }

}
