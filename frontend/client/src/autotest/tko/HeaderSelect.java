package autotest.tko;

import autotest.common.ui.DoubleListSelector;
import autotest.common.ui.SimpleHyperlink;
import autotest.common.ui.DoubleListSelector.Item;

import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.StackPanel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.List;

class HeaderSelect extends Composite implements ClickListener {
    private final static String SWITCH_TO_MULTIPLE = "Switch to multiple";
    private final static String SWITCH_TO_SINGLE = "Switch to single";
    
    private ListBox listBox = new ListBox();
    private DoubleListSelector doubleList = new DoubleListSelector();
    private StackPanel stack = new StackPanel();
    private SimpleHyperlink switchLink = new SimpleHyperlink(SWITCH_TO_MULTIPLE);
    
    public HeaderSelect() {
        stack.add(listBox);
        stack.add(doubleList);
        
        Panel panel = new VerticalPanel();
        panel.add(stack);
        panel.add(switchLink);
        initWidget(panel);
        
        switchLink.addClickListener(this);
    }
    
    public void addItem(String name, String value) {
        listBox.addItem(name, value);
        doubleList.addItem(name, value);
    }
    
    public List<Item> getSelectedItems() {
        if (!isDoubleSelectActive()) {
            copyListSelectionToDoubleList();
        }
        return doubleList.getSelectedItems();
    }

    private boolean isDoubleSelectActive() {
        return switchLink.getText().equals(SWITCH_TO_SINGLE);
    }
    
    public void selectItemsByValue(List<String> values) {
        if (values.size() > 1 && !isDoubleSelectActive()) {
            onClick(switchLink);
        }
        
        if (isDoubleSelectActive()) {
            doubleList.deselectAll();
            for (String value : values) {
                doubleList.selectItemByValue(value);
            }
        } else {
            setListBoxSelection(values.get(0));
        }
    }

    public void onClick(Widget sender) {
        assert sender == switchLink;
        if (isDoubleSelectActive()) {
            if (doubleList.getSelectedItemCount() > 0) {
                setListBoxSelection(doubleList.getSelectedItems().get(0).value);
            }
            stack.showStack(0);
            switchLink.setText(SWITCH_TO_MULTIPLE);
        } else {
            copyListSelectionToDoubleList();
            stack.showStack(1);
            switchLink.setText(SWITCH_TO_SINGLE);
        }
    }

    private void copyListSelectionToDoubleList() {
        doubleList.deselectAll();
        doubleList.selectItemByValue(getListBoxSelection());
    }

    private void setListBoxSelection(String value) {
        for (int i = 0; i < listBox.getItemCount(); i++) {
            if (listBox.getValue(i).equals(value)) {
                listBox.setSelectedIndex(i);
                return;
            }
        }
        
        throw new IllegalArgumentException("No item with value " + value);
    }

    private String getListBoxSelection() {
        return listBox.getValue(listBox.getSelectedIndex());
    }
}
