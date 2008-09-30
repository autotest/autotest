package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.DoubleListSelector;
import autotest.common.ui.SimpleHyperlink;
import autotest.common.ui.DoubleListSelector.Item;

import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.StackPanel;
import com.google.gwt.user.client.ui.TextArea;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

class HeaderSelect extends Composite implements ClickListener {
    public static final String HISTORY_FIXED_VALUES = "_fixed_values";
    
    private static final String USE_FIXED_VALUES = "Fixed values...";
    private static final String CANCEL_FIXED_VALUES = "Don't use fixed values";
    private final static String SWITCH_TO_MULTIPLE = "Switch to multiple";
    private final static String SWITCH_TO_SINGLE = "Switch to single";
    
    private ListBox listBox = new ListBox();
    private SimpleHyperlink fixedValuesLink = new SimpleHyperlink(USE_FIXED_VALUES);
    private TextArea fixedValues = new TextArea();
    private DoubleListSelector doubleList = new DoubleListSelector();
    private StackPanel stack = new StackPanel();
    private SimpleHyperlink switchLink = new SimpleHyperlink(SWITCH_TO_MULTIPLE);
    
    public HeaderSelect() {
        Panel singleHeaderOptions = new VerticalPanel();
        singleHeaderOptions.add(listBox);
        singleHeaderOptions.add(fixedValuesLink);
        singleHeaderOptions.add(fixedValues);
        stack.add(singleHeaderOptions);
        stack.add(doubleList);
        
        Panel panel = new VerticalPanel();
        panel.add(stack);
        panel.add(switchLink);
        initWidget(panel);
        
        switchLink.addClickListener(this);
        fixedValuesLink.addClickListener(this);
        fixedValues.setVisible(false);
        fixedValues.setSize("30em", "10em");
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
    
    public List<String> getFixedValues() {
        String valueText = fixedValues.getText().trim();
        if (!isFixedValuesEnabled() || valueText.equals("")) {
            return null;
        }
        
        return Utils.splitList(valueText);
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

    public void resetFixedValues() {
        if (isFixedValuesEnabled()) {
            onClick(fixedValuesLink);
        }
        fixedValues.setText("");
    }

    public void onClick(Widget sender) {
        if (sender == switchLink) {
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
        } else {
            assert sender == fixedValuesLink;
            if (isFixedValuesEnabled()) {
                fixedValues.setVisible(false);
                fixedValuesLink.setText(USE_FIXED_VALUES);
            } else {
                fixedValues.setVisible(true);
                fixedValuesLink.setText(CANCEL_FIXED_VALUES);
            }
        }
    }

    private boolean isFixedValuesEnabled() {
        return fixedValuesLink.getText().equals(CANCEL_FIXED_VALUES);
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
    
    public void addHistoryArguments(Map<String, String> arguments, String name) {
        List<String> fields = new ArrayList<String>();
        for (Item item : getSelectedItems()) {
            fields.add(item.value);
        }
        String fieldList = Utils.joinStrings(",", fields);
        arguments.put(name, fieldList);
        if (isFixedValuesEnabled()) {
            arguments.put(name + HISTORY_FIXED_VALUES, fixedValues.getText());
        }
    }
    
    public void handleHistoryArguments(Map<String, String> arguments, String name) {
        String[] fields = arguments.get(name).split(",");
        selectItemsByValue(Arrays.asList(fields));
        resetFixedValues();
        String fixedValuesText = arguments.get(name + HISTORY_FIXED_VALUES);
        fixedValues.setText(fixedValuesText);
        if (!fixedValuesText.equals("")) {
            onClick(fixedValuesLink);
        }
    }
}
