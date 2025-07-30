/**
 *
 */
package edu.ncsu.csc.CoffeeMaker.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
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
import edu.ncsu.csc.CoffeeMaker.models.enums.IngredientType;
import edu.ncsu.csc.CoffeeMaker.services.IngredientService;

/**
 * @author sheel
 *
 */
@SpringBootTest
@AutoConfigureMockMvc
@ExtendWith ( SpringExtension.class )
public class APIIngredientTest {
    /**
     * MockMvc uses Spring's testing framework to handle requests to the REST
     * API
     */
    private MockMvc               mvc;

    @Autowired
    private WebApplicationContext context;

    @Autowired
    private IngredientService     service;

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
    public void ensureIngredient () throws Exception {
        service.deleteAll();

        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 5 );
        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( coffee ) ) ).andExpect( status().isOk() );

    }

    @Test
    @Transactional
    public void testIngredientsAPI () throws Exception {

        service.deleteAll();

        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 20 );

        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( sugar ) ) );

        Assertions.assertEquals( 1, (int) service.count() );

    }

    @Test
    @Transactional
    public void testAddIngredient2 () throws Exception {

        /* Tests a recipe with a duplicate name to make sure it's rejected */

        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Ingredients in the CoffeeMaker" );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 20 );

        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( sugar ) ) );

        // mvc.perform( post( "/api/v1/ingredients" ).contentType(
        // MediaType.APPLICATION_JSON )
        // .content( TestUtils.asJsonString( sugar ) ) );
        Assertions.assertEquals( 1, service.findAll().size(), "There should only one Ingredient in the CoffeeMaker" );
    }

    @Test
    @Transactional
    public void testUpdateIngredient () throws Exception {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Ingredients in the CoffeeMaker" );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 20 );

        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( sugar ) ) );

        Assertions.assertEquals( 1, service.findAll().size(), "There should only one Ingredient in the CoffeeMaker" );

        final Ingredient sugar2 = new Ingredient( IngredientType.SUGAR, 30 );
        mvc.perform( put( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( sugar2 ) ) ).andExpect( status().isOk() );

        final String result = mvc.perform( get( "/api/v1/ingredients/{type}", IngredientType.SUGAR ) )
                .andExpect( status().isOk() ).andReturn().getResponse().getContentAsString();

        System.out.println( "RESULT: " + result );

    }

    @Test
    @Transactional
    public void testGetIngredient () throws Exception {

        /* Tests to make sure that our cap of 3 recipes is enforced */
        service.deleteAll();

        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 10 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 20 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 5 );
        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 1 );

        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( milk ) ) );
        Assertions.assertEquals( 1, (int) service.count() );

        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( coffee ) ) );
        Assertions.assertEquals( 2, (int) service.count() );

        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( sugar ) ) );
        Assertions.assertEquals( 3, (int) service.count() );

        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( chocolate ) ) );

        // Try to add a duplicate but fails.
        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( milk ) ) ).andExpect( status().isConflict() );
        Assertions.assertEquals( 4, (int) service.count() );

        final String result = mvc.perform( get( "/api/v1/ingredients/{type}", IngredientType.MILK ) )
                .andExpect( status().isOk() ).andReturn().getResponse().getContentAsString();

        final String result2 = mvc.perform( get( "/api/v1/ingredients/{type}", IngredientType.COFFEE ) )
                .andExpect( status().isOk() ).andReturn().getResponse().getContentAsString();

        final String result3 = mvc.perform( get( "/api/v1/ingredients/{type}", IngredientType.SUGAR ) )
                .andExpect( status().isOk() ).andReturn().getResponse().getContentAsString();

        final String result4 = mvc.perform( get( "/api/v1/ingredients/{type}", IngredientType.CHOCOLATE ) )
                .andExpect( status().isOk() ).andReturn().getResponse().getContentAsString();

        System.out.println( "RESULT: " + result );
        System.out.println( "RESULT: " + result2 );
        System.out.println( "RESULT: " + result3 );
        System.out.println( "RESULT: " + result4 );
    }

    @Test
    @Transactional
    public void testDeleteIngredient () throws Exception {
        /* Tests to make sure that our cap of 3 recipes is enforced */
        service.deleteAll();

        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 10 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 20 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 5 );
        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 1 );

        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( milk ) ) );
        Assertions.assertEquals( 1, (int) service.count() );

        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( coffee ) ) );
        Assertions.assertEquals( 2, (int) service.count() );

        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( sugar ) ) );
        Assertions.assertEquals( 3, (int) service.count() );

        mvc.perform( post( "/api/v1/ingredients" ).contentType( MediaType.APPLICATION_JSON )
                .content( TestUtils.asJsonString( chocolate ) ) );

        Assertions.assertEquals( 4, (int) service.count() );

        String result = mvc.perform( delete( "/api/v1/ingredients/{type}", IngredientType.MILK ) )
                .andExpect( status().isOk() ).andReturn().getResponse().getContentAsString();

        System.out.println( "RESULT: " + result );
        Assertions.assertEquals( 3, (int) service.count() );

        result = mvc.perform( delete( "/api/v1/ingredients/{type}", IngredientType.COFFEE ) )
                .andExpect( status().isOk() ).andReturn().getResponse().getContentAsString();

        System.out.println( "RESULT: " + result );
        Assertions.assertEquals( 2, (int) service.count() );

        result = mvc.perform( delete( "/api/v1/ingredients/{type}", IngredientType.SUGAR ) )
                .andExpect( status().isOk() ).andReturn().getResponse().getContentAsString();

        System.out.println( "RESULT: " + result );
        Assertions.assertEquals( 1, (int) service.count() );

        result = mvc.perform( delete( "/api/v1/ingredients/{type}", IngredientType.CHOCOLATE ) )
                .andExpect( status().isOk() ).andReturn().getResponse().getContentAsString();

        System.out.println( "RESULT: " + result );
        Assertions.assertEquals( 0, (int) service.count() );
        mvc.perform( delete( "/api/v1/ingredients/{type}", IngredientType.CHOCOLATE ) )
                .andExpect( status().isNotFound() );

    }

}
