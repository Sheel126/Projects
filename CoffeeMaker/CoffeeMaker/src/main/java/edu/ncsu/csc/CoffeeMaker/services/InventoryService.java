package edu.ncsu.csc.CoffeeMaker.services;

import java.util.List;

import javax.transaction.Transactional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Component;

import edu.ncsu.csc.CoffeeMaker.models.Inventory;
import edu.ncsu.csc.CoffeeMaker.repositories.InventoryRepository;

/**
 * InventoryService is the service used to interact with the inventory instance.
 *
 * @author Rithik Kulkarni
 */
@Component
@Transactional
public class InventoryService extends Service<Inventory, Long> {

    /**
     * This instance of the inventory repository.
     */
    @Autowired
    private InventoryRepository inventoryRepository;

    /**
     * Gets this instance of the inventory repository.
     */
    @Override
    protected JpaRepository<Inventory, Long> getRepository () {
        return inventoryRepository;
    }

    /**
     * Gets this inventory instance.
     *
     * @return the inventory instance
     */
    public synchronized Inventory getInventory () {
        final List<Inventory> inventoryList = findAll();
        if ( inventoryList != null && inventoryList.size() == 1 ) {
            return inventoryList.get( 0 );
        }
        else {
            // Initialize the inventory with 0 of everything
            final Inventory i = new Inventory();
            save( i );
            return i;
        }
    }
}
