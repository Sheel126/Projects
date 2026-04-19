package edu.ncsu.csc.CoffeeMaker.unit;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;

import javax.validation.ConstraintViolationException;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.junit.jupiter.SpringExtension;
import org.springframework.transaction.annotation.Transactional;

import edu.ncsu.csc.CoffeeMaker.TestConfig;
import edu.ncsu.csc.CoffeeMaker.models.Ingredient;
import edu.ncsu.csc.CoffeeMaker.models.Recipe;
import edu.ncsu.csc.CoffeeMaker.models.enums.IngredientType;
import edu.ncsu.csc.CoffeeMaker.services.RecipeService;

@ExtendWith ( SpringExtension.class )
@EnableAutoConfiguration
@SpringBootTest ( classes = TestConfig.class )
public class RecipeTest {

    @Autowired
    private RecipeService service;

    @BeforeEach
    public void setup () {
        service.deleteAll();
    }

    @Test
    @Transactional
    public void testAddRecipe () {

        final Recipe r1 = new Recipe();
        r1.setName( "Black Coffee" );
        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 0 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 0 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 0 );
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 1 );
        r1.addIngredient( coffee );
        r1.addIngredient( milk );
        r1.addIngredient( sugar );
        r1.addIngredient( chocolate );

        r1.setPrice( 1 );
        service.save( r1 );

        final Recipe r2 = new Recipe();
        final Ingredient chocolate2 = new Ingredient( IngredientType.CHOCOLATE, 1 );
        final Ingredient milk2 = new Ingredient( IngredientType.MILK, 1 );
        final Ingredient sugar2 = new Ingredient( IngredientType.SUGAR, 1 );
        final Ingredient coffee2 = new Ingredient( IngredientType.COFFEE, 1 );
        r2.setName( "Mocha" );
        r2.setPrice( 1 );
        r2.addIngredient( coffee2 );
        r2.addIngredient( milk2 );
        r2.addIngredient( sugar2 );
        r2.addIngredient( chocolate2 );
        service.save( r2 );

        final List<Recipe> recipes = service.findAll();
        Assertions.assertEquals( 2, recipes.size(),
                "Creating two recipes should result in two recipes in the database" );

        Assertions.assertEquals( r1, recipes.get( 0 ), "The retrieved recipe should match the created one" );
    }

    @Test
    @Transactional
    public void testNoRecipes () {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );

        final Recipe r1 = new Recipe();
        r1.setName( "Tasty Drink" );
        r1.setPrice( 12 );
        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 0 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 0 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 0 );
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, -12 );
        r1.addIngredient( coffee );
        r1.addIngredient( milk );
        r1.addIngredient( sugar );
        r1.addIngredient( chocolate );

        final Recipe r2 = new Recipe();
        final Ingredient chocolate2 = new Ingredient( IngredientType.CHOCOLATE, 1 );
        final Ingredient milk2 = new Ingredient( IngredientType.MILK, 1 );
        final Ingredient sugar2 = new Ingredient( IngredientType.SUGAR, 1 );
        final Ingredient coffee2 = new Ingredient( IngredientType.COFFEE, 1 );
        r2.setName( "Mocha" );
        r2.setPrice( 1 );
        r2.addIngredient( coffee2 );
        r2.addIngredient( milk2 );
        r2.addIngredient( sugar2 );
        r2.addIngredient( chocolate2 );

        final List<Recipe> recipes = List.of( r1, r2 );

        try {
            service.saveAll( recipes );
            Assertions.assertEquals( 0, service.count(),
                    "Trying to save a collection of elements where one is invalid should result in neither getting saved" );
        }
        catch ( final Exception e ) {
            Assertions.assertTrue( e instanceof ConstraintViolationException );
        }

    }

    @Test
    @Transactional
    public void testAddRecipe1 () {

        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );
        final String name = "Coffee";
        final Recipe r1 = createRecipe( name, 50, 3, 1, 1, 0 );

        service.save( r1 );

        Assertions.assertEquals( 1, service.findAll().size(), "There should only one recipe in the CoffeeMaker" );
        Assertions.assertNotNull( service.findByName( name ) );

    }

    /* Test2 is done via the API for different validation */

    @Test
    @Transactional
    public void testAddRecipe3 () {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );
        final String name = "Coffee";
        final Recipe r1 = createRecipe( name, -50, 3, 1, 1, 0 );

        try {
            service.save( r1 );

            Assertions.assertNull( service.findByName( name ),
                    "A recipe was able to be created with a negative price" );
        }
        catch ( final ConstraintViolationException cvee ) {
            // expected
        }

    }

    @Test
    @Transactional
    public void testAddRecipe4 () {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );
        final String name = "Coffee";
        final Recipe r1 = createRecipe( name, 50, -3, 1, 1, 2 );

        try {
            service.save( r1 );

            Assertions.assertNull( service.findByName( name ),
                    "A recipe was able to be created with a negative amount of coffee" );
        }
        catch ( final ConstraintViolationException cvee ) {
            // expected
        }

    }

    @Test
    @Transactional
    public void testAddRecipe5 () {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );
        final String name = "Coffee";
        final Recipe r1 = createRecipe( name, 50, 3, -1, 1, 2 );

        try {
            service.save( r1 );

            Assertions.assertNull( service.findByName( name ),
                    "A recipe was able to be created with a negative amount of milk" );
        }
        catch ( final ConstraintViolationException cvee ) {
            // expected
        }

    }

    @Test
    @Transactional
    public void testAddRecipe6 () {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );
        final String name = "Coffee";
        final Recipe r1 = createRecipe( name, 50, 3, 1, -1, 2 );

        try {
            service.save( r1 );

            Assertions.assertNull( service.findByName( name ),
                    "A recipe was able to be created with a negative amount of sugar" );
        }
        catch ( final ConstraintViolationException cvee ) {
            // expected
        }

    }

    @Test
    @Transactional
    public void testAddRecipe7 () {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );
        final String name = "Coffee";
        final Recipe r1 = createRecipe( name, 50, 3, 1, 1, -2 );

        try {
            service.save( r1 );

            Assertions.assertNull( service.findByName( name ),
                    "A recipe was able to be created with a negative amount of chocolate" );
        }
        catch ( final ConstraintViolationException cvee ) {
            // expected
        }

    }

    @Test
    @Transactional
    public void testAddRecipe13 () {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );

        final Recipe r1 = createRecipe( "Coffee", 50, 3, 1, 1, 0 );
        service.save( r1 );
        final Recipe r2 = createRecipe( "Mocha", 50, 3, 1, 1, 2 );
        service.save( r2 );

        Assertions.assertEquals( 2, service.count(),
                "Creating two recipes should result in two recipes in the database" );

    }

    @Test
    @Transactional
    public void testAddRecipe14 () {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );

        final Recipe r1 = createRecipe( "Coffee", 50, 3, 1, 1, 0 );
        service.save( r1 );
        final Recipe r2 = createRecipe( "Mocha", 50, 3, 1, 1, 2 );
        service.save( r2 );
        final Recipe r3 = createRecipe( "Latte", 60, 3, 2, 2, 0 );
        service.save( r3 );

        Assertions.assertEquals( 3, service.count(),
                "Creating three recipes should result in three recipes in the database" );

    }

    @Test
    @Transactional
    public void testDeleteRecipe1 () {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );

        final Recipe r1 = createRecipe( "Coffee", 50, 3, 1, 1, 0 );
        service.save( r1 );

        Assertions.assertEquals( 1, service.count(), "There should be one recipe in the database" );

        service.delete( r1 );
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );
    }

    @Test
    @Transactional
    public void testDeleteRecipe2 () {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );

        final Recipe r1 = createRecipe( "Coffee", 50, 3, 1, 1, 0 );
        service.save( r1 );
        final Recipe r2 = createRecipe( "Mocha", 50, 3, 1, 1, 2 );
        service.save( r2 );
        final Recipe r3 = createRecipe( "Latte", 60, 3, 2, 2, 0 );
        service.save( r3 );

        Assertions.assertEquals( 3, service.count(), "There should be three recipes in the database" );

        service.deleteAll();

        Assertions.assertEquals( 0, service.count(), "`service.deleteAll()` should remove everything" );

    }

    /**
     * Tests the RecipeService class
     */
    @Test
    @Transactional
    public void testDeleteRecipe3 () {
        final Recipe r = new Recipe();

        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 1 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 1 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 1 );
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 2 );

        r.setName( "Mocha" );
        r.addIngredient( coffee );
        r.addIngredient( milk );
        r.addIngredient( sugar );
        r.addIngredient( chocolate );
        r.setPrice( 350 );

        service.save( r );

        final Recipe r1 = new Recipe();

        final Ingredient chocolate2 = new Ingredient( IngredientType.CHOCOLATE, 1 );
        final Ingredient milk2 = new Ingredient( IngredientType.MILK, 1 );
        final Ingredient sugar2 = new Ingredient( IngredientType.SUGAR, 1 );
        final Ingredient coffee2 = new Ingredient( IngredientType.COFFEE, 2 );

        r1.setName( "Mocha Latte" );
        r1.addIngredient( coffee2 );
        r1.addIngredient( milk2 );
        r1.addIngredient( sugar2 );
        r1.addIngredient( chocolate2 );
        r1.setPrice( 350 );

        final List<Recipe> dbRecipesBeforeDeletion = service.findAll();
        assertEquals( 1, dbRecipesBeforeDeletion.size() );

        service.delete( r1 );

        final List<Recipe> dbRecipesAfterDeletion = service.findAll();
        assertEquals( 1, dbRecipesAfterDeletion.size() );

    }

    @Test
    @Transactional
    public void testEditRecipe1 () {
        Assertions.assertEquals( 0, service.findAll().size(), "There should be no Recipes in the CoffeeMaker" );

        final Recipe r1 = createRecipe( "Coffee", 50, 3, 1, 1, 0 );
        service.save( r1 );

        r1.setPrice( 70 );

        service.save( r1 );

        final Recipe retrieved = service.findByName( "Coffee" );

        final List<Ingredient> iList = retrieved.getIngredients();

        Assertions.assertEquals( 70, (int) retrieved.getPrice() );
        Assertions.assertEquals( 3, iList.get( 0 ).getAmount() );
        Assertions.assertEquals( 1, iList.get( 1 ).getAmount() );
        Assertions.assertEquals( 1, iList.get( 2 ).getAmount() );
        Assertions.assertEquals( 0, iList.get( 3 ).getAmount() );

        Assertions.assertEquals( 1, service.count(), "Editing a recipe shouldn't duplicate it" );

    }

    /**
     * Test if duplicate recipes are equal to each other and invalid values
     * return false on comparison.
     */
    @Test
    @Transactional
    public void testSameRecipe () {
        final Recipe r1 = createRecipe( "Coffee", 70, 3, 1, 1, 0 );
        final Recipe r2 = createRecipe( "Coffee", 70, 3, 1, 1, 0 );
        final Recipe r3 = createRecipe( "Mocha", 20, 3, 1, 1, 0 );
        final Recipe r4 = createRecipe( null, 20, 3, 1, 1, 0 );

        Assertions.assertFalse( r1.equals( null ) );
        Assertions.assertFalse( r1.equals( r3 ) );
        Assertions.assertFalse( r1.equals( r4 ) );
        Assertions.assertTrue( r1.equals( r2 ) );

    }

    /**
     * Test hashCode to make sure the hash value is the same if two objects have
     * the same name.
     */
    @Test
    @Transactional
    public void testHashCode () {
        final Recipe recipe1 = new Recipe();
        recipe1.setName( "Chocolate Coffee" );
        final Recipe recipe2 = new Recipe();
        recipe2.setName( "Chocolate Coffee" );

        final int hashCode1 = recipe1.hashCode();
        final int hashCode2 = recipe2.hashCode();

        assertEquals( hashCode1, hashCode2 );
    }

    private Recipe createRecipe ( final String name, final Integer price, final Integer coffee, final Integer milk,
            final Integer sugar, final Integer chocolate ) {
        final Recipe recipe = new Recipe();
        final Ingredient chocolate2 = new Ingredient( IngredientType.CHOCOLATE, chocolate );
        final Ingredient milk2 = new Ingredient( IngredientType.MILK, milk );
        final Ingredient sugar2 = new Ingredient( IngredientType.SUGAR, sugar );
        final Ingredient coffee2 = new Ingredient( IngredientType.COFFEE, coffee );

        recipe.setName( name );
        recipe.setPrice( price );
        recipe.addIngredient( coffee2 );
        recipe.addIngredient( milk2 );
        recipe.addIngredient( sugar2 );
        recipe.addIngredient( chocolate2 );

        return recipe;
    }

}
