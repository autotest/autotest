package autotest.common.ui;

import com.google.gwt.dom.client.Element;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FocusWidget;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class DoubleListSelector extends Composite implements ClickListener {
    private static final int VISIBLE_ITEMS = 10;
    
    private ChangeListener listener;
    private List<Item> availableList = new ArrayList<Item>(), selectedList = new ArrayList<Item>();
    private Panel container = new HorizontalPanel();
    private ListBox availableBox = new ListBox(), selectedBox = new ListBox();
    private Button addButton = new Button("Add >"), addAllButton = new Button("Add all >");
    private Button removeButton = new Button("< Remove"), 
                   removeAllButton = new Button("< Remove all");
    private Button moveUpButton = new Button("Move up"), moveDownButton = new Button("Move down");
    
    private final FocusWidget[] allWidgets = new FocusWidget[] {availableBox, selectedBox, 
            addButton, addAllButton, removeButton, removeAllButton, moveUpButton, moveDownButton};
    
    public static class Item implements Comparable<Item> {
        public String name;
        public String value;
        
        public Item(String name, String value) {
            this.name = name;
            this.value = value;
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
            return name.hashCode() * value.hashCode();
        }

        @Override
        public String toString() {
            return "Item<" + name + ", " + value + ">";
        }
    }
    
    public DoubleListSelector() {
        availableBox.setVisibleItemCount(VISIBLE_ITEMS);
        selectedBox.setVisibleItemCount(VISIBLE_ITEMS);
        
        availableBox.addClickListener(this);
        selectedBox.addClickListener(this);
        
        addAllButton.addClickListener(this);
        addButton.addClickListener(this);
        removeButton.addClickListener(this);
        removeAllButton.addClickListener(this);
        moveUpButton.addClickListener(this);
        moveDownButton.addClickListener(this);
        
        Panel moveButtonPanel = new VerticalPanel();
        moveButtonPanel.add(addAllButton);
        moveButtonPanel.add(addButton);
        moveButtonPanel.add(removeButton);
        moveButtonPanel.add(removeAllButton);
        
        Panel reorderButtonPanel = new VerticalPanel();
        reorderButtonPanel.add(moveUpButton);
        reorderButtonPanel.add(moveDownButton);
        
        container.add(availableBox);
        container.add(moveButtonPanel);
        container.add(selectedBox);
        container.add(reorderButtonPanel);
        
        initWidget(container);
        sinkEvents(Event.ONDBLCLICK);
    }
    
    public void addItem(String name, String value) {
        availableList.add(new Item(name, value));
        refresh();
    }
    
    public void removeItem(String name) {
        try {
            availableList.remove(findItem(name, availableList));
        } catch (IllegalArgumentException exc) {
            selectedList.remove(findItem(name, selectedList));
            // let exception propagate if item not found
        }
        refresh();
    }

    private void refresh() {
        Collections.sort(availableList);
        fillListBox(availableBox, availableList);
        fillListBox(selectedBox, selectedList);
    }

    private void fillListBox(ListBox listBox, List<Item> items) {
        listBox.clear();
        for (Item item : items) {
            listBox.addItem(item.name, item.value);
        }
    }

    @Override
    public void onBrowserEvent(Event event) {
        if (event.getTypeInt() != Event.ONDBLCLICK) {
            super.onBrowserEvent(event);
            return;
        }
        
        Element target = event.getTarget();
        if (availableBox.getElement().isOrHasChild(target)) {
            doSelect();
            notifyChangeListeners();
        } else if (selectedBox.getElement().isOrHasChild(target)) {
            doDeselect();
            notifyChangeListeners();
        } else {
            super.onBrowserEvent(event);
            return;
        }
        
        event.cancelBubble(true);
    }

    public void onClick(Widget sender) {
        if (sender == addAllButton) {
            selectAll();
        } else if (sender == addButton) {
            doSelect();
        } else if (sender == removeAllButton) {
            deselectAll();
        } else if (sender == removeButton) {
            doDeselect();
        } else if (sender == moveUpButton) {
            reorderItem(getSelectedItem(selectedBox), -1);
        } else if (sender == moveDownButton) {
            reorderItem(getSelectedItem(selectedBox), 1);
        }
        notifyChangeListeners();
    }

    private void reorderItem(String name, int postionDelta) {
        Item item = findItem(name, selectedList);
        int newPosition = selectedList.indexOf(item) + postionDelta;
        newPosition = Math.max(0, Math.min(selectedList.size() - 1, newPosition));
        selectedList.remove(item);
        selectedList.add(newPosition, item);
        refresh();
        selectedBox.setSelectedIndex(newPosition);
    }

    private void doDeselect() {
        String selectedItem = getSelectedItem(selectedBox);
        if (selectedItem != null) {
            deselectItem(selectedItem);
        }
    }
    
    private void doSelect() {
        String selectedItem = getSelectedItem(availableBox);
        if (selectedItem != null) {
            selectItem(selectedItem);
        }
    }

    public void deselectAll() {
        moveAll(selectedList, availableList);
    }

    public void selectAll() {
        moveAll(availableList, selectedList);
    }

    public void deselectItem(String item) {
        moveItem(item, selectedList, availableList);
    }

    public void selectItem(String item) {
        moveItem(item, availableList, selectedList);
    }
    
    public void selectItemByValue(String value) {
        selectItem(findItemByValue(value, availableList).name); 
    }
    
    private void moveAll(List<Item> from, List<Item> to) {
        for (Item item : new ArrayList<Item>(from)) {
            to.add(item);
            from.remove(item);
        }
        refresh();
    }

    private void moveItem(String name, List<Item> from, List<Item> to) {
        Item item = findItem(name, from);
        from.remove(item);
        to.add(item);
        refresh();
    }

    private void notifyChangeListeners() {
        if (listener != null) {
            listener.onChange(this);
        }
    }

    private Item findItem(String name, List<Item> list) {
        for (Item item : list) {
            if (item.name.equals(name)) {
                return item;
            }
        }
        
        throw new IllegalArgumentException("No item with name " + name);
    }
    
    private Item findItemByValue(String value, List<Item> list) {
        for (Item item : list) {
            if (item.value.equals(value)) {
                return item;
            }
        }
        
        throw new IllegalArgumentException("No item with value " + value);
    }

    private String getSelectedItem(ListBox listBox) {
        int selectedIndex = listBox.getSelectedIndex();
        if (selectedIndex == -1) {
            return null;
        }
        return listBox.getItemText(selectedIndex);
    }
    
    public List<Item> getSelectedItems() {
        List<Item> selectedItems = new ArrayList<Item>();
        for (int i = 0; i < selectedBox.getItemCount(); i++) {
            Item item = new Item(selectedBox.getItemText(i), selectedBox.getValue(i));
            selectedItems.add(item);
        }
        return selectedItems;
    }
    
    public int getSelectedItemCount() {
        return selectedBox.getItemCount();
    }
    
    public boolean isItemSelected(String name) {
        for (Item item : getSelectedItems()) {
            if (item.name.equals(name)) {
                return true;
            }
        }
        
        return false;
    }

    public void setListener(ChangeListener listener) {
        this.listener = listener;
    }
    
    public void setEnabled(boolean enabled) {
        for (FocusWidget widget : allWidgets) {
            widget.setEnabled(enabled);
        }
    }
    
    public void setMoveUpDownVisisble(boolean visible) {
        moveUpButton.setVisible(visible);
        moveDownButton.setVisible(visible);
    }
}
