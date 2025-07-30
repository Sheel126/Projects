package edu.ncsu.csc.CoffeeMaker;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;

import javax.transaction.Transactional;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.junit.jupiter.SpringExtension;

import edu.ncsu.csc.CoffeeMaker.models.Ingredient;
import edu.ncsu.csc.CoffeeMaker.models.Recipe;
import edu.ncsu.csc.CoffeeMaker.models.enums.IngredientType;
import edu.ncsu.csc.CoffeeMaker.services.RecipeService;

@ExtendWith ( SpringExtension.class )
@EnableAutoConfiguration
@SpringBootTest ( classes = TestConfig.class )

public class TestDatabaseInteraction {
    @Autowired
    private RecipeService recipeService;

    /**
     * Sets up the tests.
     */
    @BeforeEach
    public void setup () {
        recipeService.deleteAll();
    }

    /**
     * Tests the RecipeService class
     */
    @Test
    @Transactional
    public void testRecipes () {
        final Recipe r = new Recipe();

        r.setName( "Mocha" );
        r.setPrice( 350 );
        Ingredient coffee = new Ingredient( IngredientType.COFFEE, 3 );
        Ingredient sugar = new Ingredient( IngredientType.SUGAR, 1 );
        Ingredient milk = new Ingredient( IngredientType.MILK, 1 );
        Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 1 );
        r.addIngredient( coffee );
        r.addIngredient( sugar );
        r.addIngredient( milk );
        r.addIngredient( chocolate );

        recipeService.save( r );

        final List<Recipe> dbRecipes = recipeService.findAll();

        assertEquals( 1, dbRecipes.size() );

        final Recipe dbRecipe = dbRecipes.get( 0 );

        assertEquals( r.getName(), dbRecipe.getName() );
        assertEquals( r.getPrice(), dbRecipe.getPrice() );
        final List<Ingredient> iList = r.getIngredients();
        final List<Ingredient> dbList = dbRecipe.getIngredients();

        assertEquals( iList.get( 0 ), dbList.get( 0 ) );
        assertEquals( iList.get( 1 ), dbList.get( 1 ) );
        assertEquals( iList.get( 2 ), dbList.get( 2 ) );
        assertEquals( iList.get( 3 ), dbList.get( 3 ) );

        assertEquals( r, recipeService.findByName( "Mocha" ) );

        dbRecipe.setPrice( 15 );
        recipeService.save( dbRecipe );

        assertEquals( 1, recipeService.count() );
        assertEquals( 15, (int) recipeService.findAll().get( 0 ).getPrice() );

    }

}
