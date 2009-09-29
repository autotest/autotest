package autotest.common.ui;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.DoubleClickEvent;
import com.google.gwt.event.dom.client.DoubleClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.shared.GwtEvent;
import com.google.gwt.event.shared.HandlerRegistration;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;


public class MultiListSelectPresenter implements ClickHandler, DoubleClickHandler, ChangeHandler {
    /* Simple display showing two list boxes, one of available items and one of selected items */
    public interface DoubleListDisplay {
        public HasClickHandlers getAddAllButton();
        public HasClickHandlers getAddButton();
        public HasClickHandlers getRemoveButton();
        public HasClickHandlers getRemoveAllButton();
        public HasClickHandlers getMoveUpButton();
        public HasClickHandlers getMoveDownButton();
        public SimplifiedList getAvailableList();
        public SimplifiedList getSelectedList();
        // ListBoxes don't support DoubleClickEvents themselves, so the display needs to handle them
        public HandlerRegistration addDoubleClickHandler(DoubleClickHandler handler);
    }

    /* Optional additional display allowing toggle between a simple ListBox and a 
     * DoubleListSelector 
     */
    public interface ToggleDisplay {
        public SimplifiedList getSingleSelector();
        public ToggleControl getToggleMultipleLink();
        public void setDoubleListVisible(boolean doubleListVisible);
    }

    public interface GeneratorHandler {
        /**
         * The given generator Item was just selected; create and return a new generated Item.
         */
        public Item generateItem(Item generatorItem);
        
        /**
         * The given generated Item was just deselected; handle any necessary cleanup.
         */
        public void onRemoveGeneratedItem(Item generatedItem);
    }

    public static class Item implements Comparable<Item> {
        public String name;
        public String value;
        // a generator, when selected, generates a new item and selects that item instead
        public boolean isGenerator;
        // a generated item is destroyed when deselected.
        public boolean isGeneratedItem;

        private boolean selected;

        private Item(String name, String value) {
            this.name = name;
            this.value = value;
        }

        public static Item createItem(String name, String value) {
            return new Item(name, value);
        }

        public static Item createGenerator(String name, String value) {
            Item item = new Item(name, value);
            item.isGenerator = true;
            return item;
        }

        public static Item createGeneratedItem(String name, String value) {
            Item item = new Item(name, value);
            item.isGeneratedItem = true;
            return item;
        }

        public int compareTo(Item item) {
            return name.compareTo(item.name);
        }

        @Override
        public boolean equals(Object obj) {
            if (!(obj instanceof Item)) {
                return false;
            }
            Item other = (Item) obj;
            return name.equals(other.name);
        }

        @Override
        public int hashCode() {
            return name.hashCode();
        }

        @Override
        public String toString() {
            return "Item<" + name + ", " + value + ">";
        }
        
        public boolean isSelected() {
            if (isGenerator) {
                return false;
            }
            if (isGeneratedItem) {
                return true;
            }
            return selected;
        }
        
        public void setSelected(boolean selected) {
            assert !isGenerator && !isGeneratedItem;
            this.selected = selected;
        }
    }

    private static class NullToggleDisplay implements ToggleDisplay {
        @Override
        public SimplifiedList getSingleSelector() {
            return new SimplifiedList() {
                @Override
                public void addItem(String name, String value) {
                    return;
                }

                @Override
                public void clear() {
                    return;
                }

                @Override
                public String getSelectedName() {
                    return "";
                }

                @Override
                public void selectByName(String name) {
                    return;
                }

                @Override
                public HandlerRegistration addChangeHandler(ChangeHandler handler) {
                    throw new UnsupportedOperationException();
                }
            };
        }

        @Override
        public ToggleControl getToggleMultipleLink() {
            return new ToggleControl() {
                @Override
                public HandlerRegistration addClickHandler(ClickHandler handler) {
                    throw new UnsupportedOperationException();
                }

                @Override
                public void fireEvent(GwtEvent<?> event) {
                    throw new UnsupportedOperationException();
                }

                @Override
                public boolean isActive() {
                    return true;
                }

                @Override
                public void setActive(boolean active) {
                    return;
                }
            };
        }

        @Override
        public void setDoubleListVisible(boolean doubleListVisible) {
            return;
        }
    }
    
    // convenience method
    public static Set<String> getItemNameSet(List<Item> items) {
        Set<String> nameSet = new HashSet<String>();
        for (Item item : items) {
            nameSet.add(item.name);
        }
        return nameSet;
    }

    private List<Item> items = new ArrayList<Item>();
    // need a second list to track ordering
    private List<Item> selectedItems = new ArrayList<Item>();
    private DoubleListDisplay display;
    private ToggleDisplay toggleDisplay = new NullToggleDisplay();
    private GeneratorHandler generatorHandler;

    public void setGeneratorHandler(GeneratorHandler handler) {
        this.generatorHandler = handler;
    }

    public void bindDisplay(DoubleListDisplay display) {
        this.display = display;
        display.getAddAllButton().addClickHandler(this);
        display.getAddButton().addClickHandler(this);
        display.getRemoveButton().addClickHandler(this);
        display.getRemoveAllButton().addClickHandler(this);
        display.getMoveUpButton().addClickHandler(this);
        display.getMoveDownButton().addClickHandler(this);
        display.addDoubleClickHandler(this);
    }

    public void bindToggleDisplay(ToggleDisplay toggleDisplay) {
        this.toggleDisplay = toggleDisplay;
        toggleDisplay.getSingleSelector().addChangeHandler(this);
        toggleDisplay.getToggleMultipleLink().addClickHandler(this);
        toggleDisplay.getToggleMultipleLink().setActive(false);
    }

    private boolean verifyConsistency() {
        // check consistency of selectedItems
        for (Item item : items) {
            if (item.isSelected() && !selectedItems.contains(item)) {
                throw new RuntimeException("selectedItems is inconsistent, missing: " 
                                           + item.toString());
            }
        }
        return true;
    }

    public void addItem(Item item) {
        if (item.isGenerator) {
            assert generatorHandler != null : "generator items require a GeneratorHandler";
        } else if (item.isGeneratedItem && isItemPresent(item)) {
            return;
        }
        items.add(item);
        Collections.sort(items);
        if (item.isSelected()) {
            selectedItems.add(item);
        }
        assert verifyConsistency();
        refresh();
    }

    private boolean isItemPresent(Item item) {
        return Collections.binarySearch(items, item) >= 0;
    }
    
    private void removeItem(Item item) {
        items.remove(item);
        if (item.isSelected()) {
            selectedItems.remove(item);
        }
        if (item.isGeneratedItem) {
            generatorHandler.onRemoveGeneratedItem(item);
        }
        assert verifyConsistency();
        refresh();
    }

    public void removeItemByName(String name) {
        removeItem(getItemByName(name));
    }

    private void refreshSingleSelector() {
        SimplifiedList selector = toggleDisplay.getSingleSelector();

        boolean isGeneratedItemSelected = false;
        if (!selectedItems.isEmpty()) {
            assert selectedItems.size() == 1;
            isGeneratedItemSelected = selectedItems.get(0).isGeneratedItem;
        }

        selector.clear();
        for (Item item : items) {
            if (item.isGenerator && isGeneratedItemSelected) {
                continue;
            }
            selector.addItem(item.name, item.value);
            if (item.isSelected()) {
                selector.selectByName(item.name);
            }
        }
    }

    private void refreshMultipleSelector() {
        display.getAvailableList().clear();
        for (Item item : items) {
            if (!item.isSelected()) {
                display.getAvailableList().addItem(item.name, item.value);
            }
        }

        display.getSelectedList().clear();
        for (Item item : selectedItems) {
            display.getSelectedList().addItem(item.name, item.value);
        }
    }

    private void refresh() {
        if (selectedItems.size() > 1) {
            switchToMultiple();
        }
        if (isMultipleSelectActive()) {
            refreshMultipleSelector();
        } else {
            // single selector always needs something selected
            if (selectedItems.size() == 0) {
                Item firstItem = getFirstNonGenerator(); // can't default to a generator
                if (firstItem != null) {
                    selectItem(items.get(0));
                }
            }
            refreshSingleSelector();
        }
    }

    private Item getFirstNonGenerator() {
        for (Item item : items) {
            if (!item.isGenerator) {
                return item;
            }
        }
        return null;
    }

    private void selectItem(Item item) {
        if (item.isGenerator) {
            Item generatedItem = generatorHandler.generateItem(item);
            addItem(generatedItem);
        } else {
            item.setSelected(true);
            selectedItems.add(item);
        }

        assert verifyConsistency();
    }
    
    public void selectItemByName(String name) {
        selectItem(getItemByName(name));
        refresh();
    }
    
    public void setSelectedItemsByName(List<String> names) {
        for (String itemName : names) {
            Item item = getItemByName(itemName);
            if (!item.isSelected()) {
                selectItem(item);
            }
        }

        Set<String> selectedNames = new HashSet<String>(names);
        for (Item item : getItemsCopy()) {
            if (item.isSelected() && !selectedNames.contains(item.name)) {
                deselectItem(item);
            }
        }

        if (selectedItems.size() < 2) {
            switchToSingle();
        }
        refresh();
    }

    private void deselectItem(Item item) {
        if (item.isGeneratedItem) {
            removeItem(item);
        } else {
            item.setSelected(false);
            selectedItems.remove(item);
        }
        assert verifyConsistency();
    }

    public List<Item> getSelectedItems() {
        return Collections.unmodifiableList(selectedItems);
    }

    private boolean isMultipleSelectActive() {
        return toggleDisplay.getToggleMultipleLink().isActive();
    }

    private void switchToSingle() {
        // reduce selection to the first selected item
        while (selectedItems.size() > 1) {
            deselectItem(selectedItems.get(1));
        }

        toggleDisplay.setDoubleListVisible(false);
        toggleDisplay.getToggleMultipleLink().setActive(false);
    }

    private void switchToMultiple() {
        toggleDisplay.setDoubleListVisible(true);
        toggleDisplay.getToggleMultipleLink().setActive(true);
    }

    private Item getItemByName(String name) {
        for (Item item : items) {
            if (item.name.equals(name)) {
                return item;
            }
        }
        
        throw new IllegalArgumentException("Item '" + name + "' does not exist in " + items);
    }

    @Override
    public void onClick(ClickEvent event) {
        boolean isItemSelectedOnLeft = (display.getAvailableList().getSelectedName() != null);
        boolean isItemSelectedOnRight = (display.getSelectedList().getSelectedName() != null);
        Object source = event.getSource();
        if (source == display.getAddAllButton()) {
            addAll();
        } else if (source == display.getAddButton() && isItemSelectedOnLeft) {
            doSelect();
        } else if (source == display.getRemoveButton() && isItemSelectedOnRight) {
            doDeselect();
        } else if (source == display.getRemoveAllButton()) {
            deselectAll();
        } else if ((source == display.getMoveUpButton() || source == display.getMoveDownButton())
                   && isItemSelectedOnRight) {
            reorderItem(source == display.getMoveUpButton());
            return; // don't refresh again or we'll mess up the user's selection
        } else if (source == toggleDisplay.getToggleMultipleLink()) {
            if (toggleDisplay.getToggleMultipleLink().isActive()) {
                switchToMultiple();
            } else {
                switchToSingle();
            }
        } else {
            throw new RuntimeException("Unexpected ClickEvent from " + event.getSource());
        }
        
        refresh();
    }

    @Override
    public void onDoubleClick(DoubleClickEvent event) {
        Object source = event.getSource();
        if (source == display.getAvailableList()) {
            doSelect();
        } else if (source == display.getSelectedList()) {
            doDeselect();
        } else {
            // ignore double-clicks on other widgets
            return;
        }
        
        refresh();
    }

    @Override
    public void onChange(ChangeEvent event) {
        assert toggleDisplay != null;
        SimplifiedList selector = toggleDisplay.getSingleSelector();
        assert event.getSource() == selector;
        // events should only come from the single selector when it's active
        assert !toggleDisplay.getToggleMultipleLink().isActive();

        for (Item item : getItemsCopy()) {
            if (item.isSelected()) {
                deselectItem(item);
            } else if (item.name.equals(selector.getSelectedName())) {
                selectItem(item);
            }
        }
        
        refresh();
    }

    /**
     * Selecting or deselecting items can add or remove items (due to generators), so sometimes we
     * need to iterate over a copy.
     */
    private Iterable<Item> getItemsCopy() {
        return new ArrayList<Item>(items);
    }

    private void doSelect() {
        selectItem(getItemByName(display.getAvailableList().getSelectedName()));
    }

    private void doDeselect() {
        deselectItem(getItemByName(display.getSelectedList().getSelectedName()));
    }

    private void addAll() {
        for (Item item : items) {
            if (!item.isSelected() && !item.isGenerator) {
                selectItem(item);
            }
        }
    }

    public void deselectAll() {
        for (Item item : getItemsCopy()) {
            if (item.isSelected()) {
                deselectItem(item);
            }
        }
    }

    private void reorderItem(boolean moveUp) {
        Item item = getItemByName(display.getSelectedList().getSelectedName());
        int positionDelta = moveUp ? -1 : 1;
        int newPosition = selectedItems.indexOf(item) + positionDelta;
        newPosition = Math.max(0, Math.min(selectedItems.size() - 1, newPosition));
        selectedItems.remove(item);
        selectedItems.add(newPosition, item);
        refresh();
        display.getSelectedList().selectByName(item.name);
    }
}
