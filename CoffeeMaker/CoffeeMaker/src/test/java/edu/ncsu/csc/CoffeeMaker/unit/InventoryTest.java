package edu.ncsu.csc.CoffeeMaker.unit;

import java.util.List;

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
import edu.ncsu.csc.CoffeeMaker.models.Inventory;
import edu.ncsu.csc.CoffeeMaker.models.Recipe;
import edu.ncsu.csc.CoffeeMaker.models.enums.IngredientType;
import edu.ncsu.csc.CoffeeMaker.services.InventoryService;

@ExtendWith ( SpringExtension.class )
@EnableAutoConfiguration
@SpringBootTest ( classes = TestConfig.class )
public class InventoryTest {

    @Autowired
    private InventoryService inventoryService;

    @BeforeEach
    public void setup () {
        final Inventory ivt = inventoryService.getInventory();

        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 500 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 500 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 500 );
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 500 );
        ivt.addIngredients( chocolate );
        ivt.addIngredients( coffee );
        ivt.addIngredients( milk );
        ivt.addIngredients( sugar );

        inventoryService.save( ivt );
    }

    @Test
    @Transactional
    public void testConsumeInventory () {
        final Inventory i = inventoryService.getInventory();

        final Recipe recipe = new Recipe();
        recipe.setName( "Delicious Not-Coffee" );
        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 10 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 20 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 5 );
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 1 );
        recipe.addIngredient( coffee );
        recipe.addIngredient( milk );
        recipe.addIngredient( sugar );
        recipe.addIngredient( chocolate );

        recipe.setPrice( 5 );

        i.useIngredients( recipe );

        /*
         * Make sure that all of the inventory fields are now properly updated
         */

        Assertions.assertEquals( 490, i.getIngredient( IngredientType.CHOCOLATE ).getAmount() );
        Assertions.assertEquals( 480, i.getIngredient( IngredientType.MILK ).getAmount() );
        Assertions.assertEquals( 495, i.getIngredient( IngredientType.SUGAR ).getAmount() );
        Assertions.assertEquals( 499, i.getIngredient( IngredientType.COFFEE ).getAmount() );
    }

    /**
     * Tests functionality and exceptions for checkChocolate in Inventory
     */
    @Test
    @Transactional
    public void testCheckChocolate () {
        final Inventory i = inventoryService.getInventory();

        final Recipe recipe = new Recipe();
        recipe.setName( "Delicious Not-Coffee" );

        final Exception e1 = Assertions.assertThrows( IllegalArgumentException.class,
                () -> i.checkIngredient( "five" ) );
        Assertions.assertEquals( "Units of ingredient must be a positive integer", e1.getMessage() );

        final Exception e2 = Assertions.assertThrows( IllegalArgumentException.class, () -> i.checkIngredient( "-5" ) );
        Assertions.assertEquals( "Units of ingredient must be a positive integer", e2.getMessage() );

        final Integer chocolate = i.checkIngredient( "5" );

        final Ingredient chocolate1 = new Ingredient( IngredientType.CHOCOLATE, chocolate );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 20 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 5 );
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 1 );
        recipe.addIngredient( coffee );
        recipe.addIngredient( milk );
        recipe.addIngredient( sugar );
        recipe.addIngredient( chocolate1 );

        recipe.setPrice( 5 );

        i.useIngredients( recipe );

        /*
         * Make sure that all of the inventory fields are now properly updated
         */

        Assertions.assertEquals( 495, i.getIngredient( IngredientType.CHOCOLATE ).getAmount() );
        Assertions.assertEquals( 480, i.getIngredient( IngredientType.MILK ).getAmount() );
        Assertions.assertEquals( 495, i.getIngredient( IngredientType.SUGAR ).getAmount() );
        Assertions.assertEquals( 499, i.getIngredient( IngredientType.COFFEE ).getAmount() );
    }

    /**
     * Tests functionality and exceptions for checkMilk in Inventory
     */
    @Test
    @Transactional
    public void testCheckMilk () {
        final Inventory i = inventoryService.getInventory();

        final Recipe recipe = new Recipe();
        recipe.setName( "Delicious Not-Coffee" );

        final Exception e1 = Assertions.assertThrows( IllegalArgumentException.class,
                () -> i.checkIngredient( "five" ) );
        Assertions.assertEquals( "Units of ingredient must be a positive integer", e1.getMessage() );

        final Exception e2 = Assertions.assertThrows( IllegalArgumentException.class, () -> i.checkIngredient( "-5" ) );
        Assertions.assertEquals( "Units of ingredient must be a positive integer", e2.getMessage() );

        final Integer milk = i.checkIngredient( "5" );

        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 5 );
        final Ingredient milk1 = new Ingredient( IngredientType.MILK, milk );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 5 );
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 1 );
        recipe.addIngredient( coffee );
        recipe.addIngredient( milk1 );
        recipe.addIngredient( sugar );
        recipe.addIngredient( chocolate );

        recipe.setPrice( 5 );

        i.useIngredients( recipe );

        /*
         * Make sure that all of the inventory fields are now properly updated
         */

        Assertions.assertEquals( 495, i.getIngredient( IngredientType.CHOCOLATE ).getAmount() );
        Assertions.assertEquals( 495, i.getIngredient( IngredientType.MILK ).getAmount() );
        Assertions.assertEquals( 495, i.getIngredient( IngredientType.SUGAR ).getAmount() );
        Assertions.assertEquals( 499, i.getIngredient( IngredientType.COFFEE ).getAmount() );
    }

    /**
     * Tests functionality and exceptions for checkCoffee in Inventory
     */
    @Test
    @Transactional
    public void testCheckCoffee () {
        final Inventory i = inventoryService.getInventory();

        final Recipe recipe = new Recipe();
        recipe.setName( "Delicious Not-Coffee" );

        final Exception e1 = Assertions.assertThrows( IllegalArgumentException.class,
                () -> i.checkIngredient( "five" ) );
        Assertions.assertEquals( "Units of ingredient must be a positive integer", e1.getMessage() );

        final Exception e2 = Assertions.assertThrows( IllegalArgumentException.class, () -> i.checkIngredient( "-5" ) );
        Assertions.assertEquals( "Units of ingredient must be a positive integer", e2.getMessage() );

        final Integer coffee = i.checkIngredient( "5" );

        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 5 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 5 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 5 );
        final Ingredient coffee1 = new Ingredient( IngredientType.COFFEE, coffee );
        recipe.addIngredient( coffee1 );
        recipe.addIngredient( milk );
        recipe.addIngredient( sugar );
        recipe.addIngredient( chocolate );

        recipe.setPrice( 5 );

        i.useIngredients( recipe );

        /*
         * Make sure that all of the inventory fields are now properly updated
         */

        Assertions.assertEquals( 495, i.getIngredient( IngredientType.CHOCOLATE ).getAmount() );
        Assertions.assertEquals( 495, i.getIngredient( IngredientType.MILK ).getAmount() );
        Assertions.assertEquals( 495, i.getIngredient( IngredientType.SUGAR ).getAmount() );
        Assertions.assertEquals( 495, i.getIngredient( IngredientType.COFFEE ).getAmount() );
    }

    /**
     * Tests functionality and exceptions for checkMilk in Inventory
     */
    @Test
    @Transactional
    public void testCheckSugar () {
        final Inventory i = inventoryService.getInventory();

        final Recipe recipe = new Recipe();
        recipe.setName( "Delicious Not-Coffee" );

        final Exception e1 = Assertions.assertThrows( IllegalArgumentException.class,
                () -> i.checkIngredient( "five" ) );
        Assertions.assertEquals( "Units of ingredient must be a positive integer", e1.getMessage() );

        final Exception e2 = Assertions.assertThrows( IllegalArgumentException.class, () -> i.checkIngredient( "-5" ) );
        Assertions.assertEquals( "Units of ingredient must be a positive integer", e2.getMessage() );

        final Integer sugar = i.checkIngredient( "5" );

        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 5 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 5 );
        final Ingredient sugar1 = new Ingredient( IngredientType.SUGAR, sugar );
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 1 );
        recipe.addIngredient( coffee );
        recipe.addIngredient( milk );
        recipe.addIngredient( sugar1 );
        recipe.addIngredient( chocolate );

        recipe.setPrice( 5 );

        i.useIngredients( recipe );

        /*
         * Make sure that all of the inventory fields are now properly updated
         */
        Assertions.assertEquals( 495, i.getIngredient( IngredientType.CHOCOLATE ).getAmount() );
        Assertions.assertEquals( 495, i.getIngredient( IngredientType.MILK ).getAmount() );
        Assertions.assertEquals( 495, i.getIngredient( IngredientType.SUGAR ).getAmount() );
        Assertions.assertEquals( 499, i.getIngredient( IngredientType.COFFEE ).getAmount() );
    }

    @Test
    @Transactional
    public void testAddInventory1 () {
        Inventory ivt = inventoryService.getInventory();

        ivt.updateIngredientValues( IngredientType.COFFEE, 5 );
        ivt.updateIngredientValues( IngredientType.MILK, 3 );
        ivt.updateIngredientValues( IngredientType.SUGAR, 7 );
        ivt.updateIngredientValues( IngredientType.CHOCOLATE, 2 );

        /* Save and retrieve again to update with DB */
        inventoryService.save( ivt );

        ivt = inventoryService.getInventory();

        Assertions.assertEquals( 505, ivt.getIngredient( IngredientType.COFFEE ).getAmount(),
                "Adding to the inventory should result in correctly-updated values for coffee" );
        Assertions.assertEquals( 503, ivt.getIngredient( IngredientType.MILK ).getAmount(),
                "Adding to the inventory should result in correctly-updated values for milk" );
        Assertions.assertEquals( 507, ivt.getIngredient( IngredientType.SUGAR ).getAmount(),
                "Adding to the inventory should result in correctly-updated values sugar" );
        Assertions.assertEquals( 502, ivt.getIngredient( IngredientType.CHOCOLATE ).getAmount(),
                "Adding to the inventory should result in correctly-updated values chocolate" );

    }

    @Test
    @Transactional
    public void testAddInventory2 () {
        final Inventory ivt = inventoryService.getInventory();

        try {
            // ivt.addIngredients( -5, 3, 7, 2 );
            ivt.updateIngredientValues( IngredientType.COFFEE, -5 );
            ivt.updateIngredientValues( IngredientType.MILK, 3 );
            ivt.updateIngredientValues( IngredientType.SUGAR, 7 );
            ivt.updateIngredientValues( IngredientType.CHOCOLATE, 2 );
        }
        catch ( final IllegalArgumentException iae ) {
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.COFFEE ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- coffee" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.MILK ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- milk" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.SUGAR ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- sugar" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.CHOCOLATE ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- chocolate" );
        }
    }

    @Test
    @Transactional
    public void testAddInventory3 () {
        final Inventory ivt = inventoryService.getInventory();

        try {
            ivt.updateIngredientValues( IngredientType.MILK, -3 );
        }
        catch ( final IllegalArgumentException iae ) {
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.COFFEE ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- coffee" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.MILK ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- milk" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.SUGAR ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- sugar" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.CHOCOLATE ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- chocolate" );

        }

    }

    @Test
    @Transactional
    public void testAddInventory4 () {
        final Inventory ivt = inventoryService.getInventory();

        try {
            ivt.updateIngredientValues( IngredientType.SUGAR, -7 );

        }
        catch ( final IllegalArgumentException iae ) {
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.COFFEE ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- coffee" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.MILK ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- milk" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.SUGAR ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- sugar" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.CHOCOLATE ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- chocolate" );

        }

    }

    @Test
    @Transactional
    public void testAddInventory5 () {
        final Inventory ivt = inventoryService.getInventory();

        try {
            ivt.updateIngredientValues( IngredientType.CHOCOLATE, -2 );
        }
        catch ( final IllegalArgumentException iae ) {
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.COFFEE ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- coffee" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.MILK ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- milk" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.SUGAR ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- sugar" );
            Assertions.assertEquals( 500, ivt.getIngredient( IngredientType.CHOCOLATE ).getAmount(),
                    "Trying to update the Inventory with an invalid value for coffee should result in no changes -- chocolate" );

        }

    }

    /**
     * Test enoughIngreidents to see if there are enough ingredients to make the
     * beverage. Return true if there are and false otherwise
     */
    @Test
    @Transactional
    public void enoughIngredients () {
        final Inventory ivt = inventoryService.getInventory();
        final Recipe recipe = new Recipe();
        recipe.setName( "Delicious Not-Coffee" );

        final Ingredient chocolate = new Ingredient( IngredientType.CHOCOLATE, 1 );
        final Ingredient milk = new Ingredient( IngredientType.MILK, 2 );
        final Ingredient sugar = new Ingredient( IngredientType.SUGAR, 5 );
        final Ingredient coffee = new Ingredient( IngredientType.COFFEE, 1 );
        recipe.addIngredient( chocolate );
        recipe.addIngredient( milk );
        recipe.addIngredient( sugar );
        recipe.addIngredient( coffee );

        recipe.setPrice( 5 );

        final List<Ingredient> iList = recipe.getIngredients();

        iList.get( 1 ).setAmount( 2000 );
        Assertions.assertFalse( ivt.enoughIngredients( recipe ) );
        iList.get( 1 ).setAmount( 2 );

        iList.get( 0 ).setAmount( 1000 );
        Assertions.assertFalse( ivt.enoughIngredients( recipe ) );
        iList.get( 0 ).setAmount( 1 );

        iList.get( 3 ).setAmount( 1000 );
        Assertions.assertFalse( ivt.enoughIngredients( recipe ) );
        iList.get( 3 ).setAmount( 1 );

        iList.get( 2 ).setAmount( 1000 );
        Assertions.assertFalse( ivt.enoughIngredients( recipe ) );
        iList.get( 2 ).setAmount( 5 );

        Assertions.assertTrue( ivt.enoughIngredients( recipe ) );

    }

    /**
     * Tests functionality for toString in Inventory
     */
    @Test
    @Transactional
    public void testToString () {
        final Inventory inventory = new Inventory( 1, 2, 3, 4 );

        final String result = inventory.toString();

        final String expected = "Ingredient [ingredient=COFFEE, amount=1]\n"
                + "Ingredient [ingredient=MILK, amount=2]\n" + "Ingredient [ingredient=SUGAR, amount=3]\n"
                + "Ingredient [ingredient=CHOCOLATE, amount=4]\n";
        Assertions.assertEquals( expected, result );
    }

}
