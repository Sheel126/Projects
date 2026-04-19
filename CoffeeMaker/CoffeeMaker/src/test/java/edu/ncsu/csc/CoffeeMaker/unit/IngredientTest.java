package edu.ncsu.csc.CoffeeMaker.unit;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;

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
import edu.ncsu.csc.CoffeeMaker.models.enums.IngredientType;
import edu.ncsu.csc.CoffeeMaker.services.IngredientService;

@ExtendWith ( SpringExtension.class )
@EnableAutoConfiguration
@SpringBootTest ( classes = TestConfig.class )
public class IngredientTest {

    @Autowired
    private IngredientService ingredientService;

    @BeforeEach
    public void setup () {
        ingredientService.deleteAll();
    }

    @Test
    public void testConstructor () {
        final Ingredient ingredient = new Ingredient( IngredientType.COFFEE, 10 );
        assertEquals( IngredientType.COFFEE, ingredient.getIngredient(), "Ingredient type should be COFFEE" );
        assertEquals( 10, ingredient.getAmount(), "Amount should be 10" );
    }

    @Test
    public void testSetIngredient () {
        final Ingredient ingredient = new Ingredient();
        ingredient.setIngredient( IngredientType.MILK );
        assertEquals( IngredientType.MILK, ingredient.getIngredient(), "Ingredient type should be MILK" );
    }

    @Test
    public void testSetAmount () {
        final Ingredient ingredient = new Ingredient();
        ingredient.setAmount( 5 );
        assertEquals( 5, ingredient.getAmount(), "Amount should be 5" );
    }

    @Test
    public void testToString () {
        final Ingredient ingredient = new Ingredient( IngredientType.SUGAR, 3 );
        assertEquals( "Ingredient [ingredient=SUGAR, amount=3]", ingredient.toString(),
                "String representation should match" );
    }

    @Test
    @Transactional
    public void testSaveIngredient () {
        ingredientService.deleteAll();
        final Ingredient ingredient1 = new Ingredient( IngredientType.COFFEE, 10 );
        final Ingredient ingredient2 = new Ingredient( IngredientType.MILK, 15 );

        ingredientService.save( ingredient1 );
        ingredientService.save( ingredient2 );

        final List<Ingredient> savedIngredients = ingredientService.findAll();
        assertEquals( 2, savedIngredients.size(), "Two ingredients should be saved" );

        final Ingredient savedIngredient1 = savedIngredients.get( 0 );
        final Ingredient savedIngredient2 = savedIngredients.get( 1 );

        assertEquals( ingredient1.getIngredient(), savedIngredient1.getIngredient(), "Ingredient types should match" );
        assertEquals( ingredient1.getAmount(), savedIngredient1.getAmount(), "Amounts should match" );

        assertEquals( ingredient2.getIngredient(), savedIngredient2.getIngredient(), "Ingredient types should match" );
        assertEquals( ingredient2.getAmount(), savedIngredient2.getAmount(), "Amounts should match" );
    }

    @Test
    @Transactional
    public void testDeleteIngredient () {
        final Ingredient ingredient1 = new Ingredient( IngredientType.COFFEE, 10 );
        final Ingredient ingredient2 = new Ingredient( IngredientType.MILK, 5 );

        ingredientService.save( ingredient1 );
        ingredientService.save( ingredient2 );

        List<Ingredient> savedIngredients = ingredientService.findAll();
        assertEquals( 2, savedIngredients.size(), "Two ingredients should be saved" );

        ingredientService.delete( ingredient1 );

        savedIngredients = ingredientService.findAll();
        assertEquals( 1, savedIngredients.size(), "One ingredient should be deleted" );

        assertEquals( IngredientType.MILK, savedIngredients.get( 0 ).getIngredient(),
                "Remaining ingredient should be MILK" );
        assertEquals( 5, savedIngredients.get( 0 ).getAmount(), "Amount of remaining ingredient should be 5" );
    }

}
