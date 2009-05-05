package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.DoubleListSelector;
import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.SimpleHyperlink;
import autotest.common.ui.DoubleListSelector.Item;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.StackPanel;
import com.google.gwt.user.client.ui.TextArea;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

class HeaderSelect extends Composite implements ClickListener, ChangeListener {
    public static final String HISTORY_FIXED_VALUES = "_fixed_values";
    
    private static final String USE_FIXED_VALUES = "Fixed values...";
    private static final String CANCEL_FIXED_VALUES = "Don't use fixed values";
    private final static String SWITCH_TO_MULTIPLE = "Switch to multiple";
    private final static String SWITCH_TO_SINGLE = "Switch to single";
    private final static HeaderField MACHINE_LABELS_FIELD = 
        new SimpleHeaderField("Machine labels...", "");
    
    private static class MachineLabelInput extends Composite implements ChangeListener {
        public MachineLabelField headerField;
        private TextBox labelInput = new TextBox();
        
        public MachineLabelInput(MachineLabelField headerField) {
            this.headerField = headerField;
            Panel container = new HorizontalPanel();
            container.add(new Label(headerField.getName() + ": "));
            container.add(labelInput);
            initWidget(container);
            
            labelInput.setText(Utils.joinStrings(",", headerField.getLabelList()));
            labelInput.addChangeListener(this);
        }
        
        public void onChange(Widget sender) {
            updateFieldFromInput();
        }

        public void updateFieldFromInput() {
            List<String> labelList = Utils.splitListWithSpaces(labelInput.getText());
            headerField.setLabels(labelList);
        }

        public void setText(String text) {
            labelInput.setText(text);
            updateFieldFromInput();
        }
    }

    private Map<String, HeaderField> headerMap = new HashMap<String, HeaderField>();
    private Map<MachineLabelField, MachineLabelInput> machineLabelInputMap = 
        new HashMap<MachineLabelField, MachineLabelInput>();

    private ExtendedListBox listBox = new ExtendedListBox();
    private SimpleHyperlink fixedValuesLink = new SimpleHyperlink(USE_FIXED_VALUES);
    private TextArea fixedValues = new TextArea();
    private DoubleListSelector doubleList = new DoubleListSelector();
    private StackPanel stack = new StackPanel();
    private SimpleHyperlink switchLink = new SimpleHyperlink(SWITCH_TO_MULTIPLE);
    private Panel machineLabelInputPanel = new VerticalPanel();
    
    private List<HeaderField> savedSelectedFields;
    private String savedFixedValues;
    
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
        panel.add(machineLabelInputPanel);
        initWidget(panel);
        
        switchLink.addClickListener(this);
        fixedValuesLink.addClickListener(this);
        fixedValues.setVisible(false);
        fixedValues.setSize("30em", "10em");
        
        listBox.addChangeListener(this);
        doubleList.setListener(this);
        addItem(MACHINE_LABELS_FIELD);
    }

    public void addItem(HeaderField headerField) {
        headerMap.put(headerField.getSqlName(), headerField);
        refreshSingleList();
        doubleList.addItem(headerField.getName(), headerField.getSqlName());
    }

    private void removeItem(HeaderField header) {
        HeaderField mappedHeader = headerMap.remove(header.getSqlName());
        assert mappedHeader == header;
        refreshSingleList();
        doubleList.removeItem(header.getName());
    }

    private List<HeaderField> getHeaderFields() {
        // create a copy so we can iterate + modify the map
        return new ArrayList<HeaderField>(headerMap.values());
    }
    
    private List<HeaderField> getSortedFields() {
        List<HeaderField> fields = getHeaderFields();
        Collections.sort(fields);
        return fields;
    }
    
    private void refreshSingleList() {
        String selectedValue = listBox.getSelectedValue();
        HeaderField selectedField = headerMap.get(selectedValue);
        listBox.clear();
        for (HeaderField field : getSortedFields()) {
            if (field == MACHINE_LABELS_FIELD && selectedField instanceof MachineLabelField) {
                // don't show "Machine labels..." option if one is already selected
                continue;
            }
            listBox.addItem(field.getName(), field.getSqlName());
        }
        
        if (selectedValue != null) {
            try {
                listBox.selectByValue(selectedValue);
            } catch (IllegalArgumentException exc) {
                // selected item was removed
            }
        }
    }
    
    public void updateStateFromView() {
        savedSelectedFields = getSelectedItemsFromView();
        savedFixedValues = getFixedValuesText();
        updateMachineLabelsFromView();
    }
    
    private List<HeaderField> getSelectedItemsFromView() {
        if (!isDoubleSelectActive()) {
            copyListSelectionToDoubleList();
        }
        
        List<HeaderField> selectedFields = new ArrayList<HeaderField>();
        for (Item item : doubleList.getSelectedItems()) {
            selectedFields.add(headerMap.get(item.value));
        }
        return selectedFields;
    }
    
    private String getFixedValuesText() {
        if (!isFixedValuesEnabled()) {
            return "";
        }
        
        return fixedValues.getText();
    }
    
    public List<HeaderField> getSelectedItems() {
        return Collections.unmodifiableList(savedSelectedFields);
    }
    
    public void updateViewFromState() {
        selectItemsInView(savedSelectedFields);
        resetFixedValues();
        fixedValues.setText(savedFixedValues);
        if (!savedFixedValues.equals("")) {
            onClick(fixedValuesLink);
        }
    }
    
    private void selectItemsInView(List<HeaderField> fields) {
        addNecessaryMachineLabelFields(fields);
        
        if (fields.size() > 1 && !isDoubleSelectActive()) {
            showDoubleList();
        }
        
        if (isDoubleSelectActive()) {
            doubleList.deselectAll();
            for (HeaderField field : fields) {
                doubleList.selectItemByValue(field.getSqlName());
            }
            onChange(doubleList);
        } else {
            listBox.selectByName(fields.get(0).getName());
            onChange(listBox);
        }
    }

    private void resetFixedValues() {
        if (isFixedValuesEnabled()) {
            onClick(fixedValuesLink);
        }
        fixedValues.setText("");
    }

    private boolean isDoubleSelectActive() {
        return switchLink.getText().equals(SWITCH_TO_SINGLE);
    }
    
    public void selectItems(List<HeaderField> fields) {
        savedSelectedFields = new ArrayList<HeaderField>(fields);
        savedFixedValues = "";
    }
    
    public void selectItem(HeaderField field) {
        selectItems(Arrays.asList(new HeaderField[] {field}));
    }
    
    private void addNecessaryMachineLabelFields(List<HeaderField> fields) {
        removeAllMachineLabelHeadersExcept(null);
        for (HeaderField field : fields) {
            if (field instanceof MachineLabelField) {
                addExistingMachineLabelField((MachineLabelField) field);
            }
        }
    }

    public void onClick(Widget sender) {
        if (sender == switchLink) {
            if (isDoubleSelectActive()) {
                if (doubleList.getSelectedItemCount() > 0) {
                    listBox.selectByName(doubleList.getSelectedItems().get(0).name);
                }
                showSingleList();
                onChange(listBox);
            } else {
                copyListSelectionToDoubleList();
                showDoubleList();
                onChange(doubleList);
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

    private void showSingleList() {
        stack.showStack(0);
        switchLink.setText(SWITCH_TO_MULTIPLE);
    }

    private void showDoubleList() {
        stack.showStack(1);
        switchLink.setText(SWITCH_TO_SINGLE);
    }

    private boolean isFixedValuesEnabled() {
        return fixedValuesLink.getText().equals(CANCEL_FIXED_VALUES);
    }

    private void copyListSelectionToDoubleList() {
        doubleList.deselectAll();
        doubleList.selectItemByValue(getListBoxSelection());
    }

    private String getListBoxSelection() {
        return listBox.getValue(listBox.getSelectedIndex());
    }
    
    public void addHistoryArguments(Map<String, String> arguments, String name) {
        List<String> fields = new ArrayList<String>();
        for (HeaderField field : getSelectedItems()) {
            fields.add(field.getSqlName());
        }
        String fieldList = Utils.joinStrings(",", fields);
        arguments.put(name, fieldList);
        if (isFixedValuesEnabled()) {
            arguments.put(name + HISTORY_FIXED_VALUES, fixedValues.getText());
        }
        
        for (MachineLabelField field : getMachineLabelHeaders()) {
            String labels = Utils.joinStrings(",", field.getLabelList());
            arguments.put(field.getSqlName(), labels);
        }
    }
    
    public void handleHistoryArguments(Map<String, String> arguments, String name) {
        List<HeaderField> headerFields = getHeaderFieldsFromValues(arguments, name);
        selectItems(headerFields);
        String fixedValuesText = arguments.get(name + HISTORY_FIXED_VALUES);
        fixedValues.setText(fixedValuesText);
        if (!fixedValuesText.equals("")) {
            onClick(fixedValuesLink);
        }
    }

    private List<HeaderField> getHeaderFieldsFromValues(Map<String, String> arguments, 
                                                        String name) {
        String[] fields = arguments.get(name).split(",");
        List<HeaderField> headerFields = new ArrayList<HeaderField>();
        for (String field : fields) {
            if (field.startsWith(MachineLabelField.BASE_SQL_NAME)) {
                MachineLabelField machineLabelField = addMachineLabelField(field);
                machineLabelInputMap.get(machineLabelField).setText(arguments.get(field));
            }

            headerFields.add(headerMap.get(field));
        }
        return headerFields;
    }

    private boolean isItemSelected(HeaderField field) {
        return getSelectedItems().contains(field);
    }

    public void onChange(Widget sender) {
        if (sender == listBox) {
            HeaderField selectedHeader = headerMap.get(listBox.getSelectedValue());
            if (selectedHeader == MACHINE_LABELS_FIELD) {
                MachineLabelField field = addMachineLabelField();
                listBox.selectByName(field.getName());
            } else {
                removeAllMachineLabelHeadersExcept(selectedHeader);
            }
            refreshSingleList();
        } else {
            assert sender == doubleList;
            if (isItemSelected(MACHINE_LABELS_FIELD)) {
                doubleList.deselectItem(MACHINE_LABELS_FIELD.getName());
                MachineLabelField field = addMachineLabelField();
                doubleList.selectItem(field.getName());
            }

            for (HeaderField header : getHeaderFields()) {
                if (header instanceof MachineLabelField && !isItemSelected(header)) {
                    removeMachineLabelField(header);
                }
            }
        }
    }

    private MachineLabelField addMachineLabelField(String name) {
        MachineLabelField field;
        if (name != null) {
            field = MachineLabelField.fromFieldName(name);
        } else {
            field = MachineLabelField.newInstance();
        }

        return addExistingMachineLabelField(field);
    }

    private MachineLabelField addExistingMachineLabelField(MachineLabelField field) {
        addItem(field);
        MachineLabelInput input = new MachineLabelInput(field);
        machineLabelInputMap.put(field, input);
        machineLabelInputPanel.add(input);
        return field;
    }
    
    private MachineLabelField addMachineLabelField() {
        return addMachineLabelField(null);
    }

    private void removeMachineLabelField(HeaderField field) {
        removeItem(field);
        MachineLabelInput input = machineLabelInputMap.remove(field);
        machineLabelInputPanel.remove(input);
    }

    private void removeAllMachineLabelHeadersExcept(HeaderField except) {
        for (HeaderField header : getHeaderFields()) {
            if (header instanceof MachineLabelField && header != except) {
                removeMachineLabelField(header);
            }
        }
    }
    
    private void updateMachineLabelsFromView() {
        for (MachineLabelInput input : machineLabelInputMap.values()) {
            input.updateFieldFromInput();
        }
    }
    
    private List<MachineLabelField> getMachineLabelHeaders() {
        return new ArrayList<MachineLabelField>(machineLabelInputMap.keySet());
    }
    
    /**
     * @return true if all machine label header inputs are not empty.
     */
    public boolean checkMachineLabelHeaders() {
        for (MachineLabelField field : getMachineLabelHeaders()) {
            if (field.getLabelList().isEmpty()) {
                return false;
            }
        }
        return true;
    }

    public void addQueryParameters(JSONObject parameters) {
        for (HeaderField field : getSelectedItems()) {
            field.addQueryParameters(parameters);
        }

        List<String> fixedValues = getFixedValues();
        if (fixedValues != null) {
            JSONObject fixedValuesObject = 
                Utils.setDefaultValue(parameters, "fixed_headers", new JSONObject()).isObject();
            fixedValuesObject.put(getSelectedItems().get(0).getSqlName(), 
                            Utils.stringsToJSON(fixedValues));
        }
    }

    private List<String> getFixedValues() {
        String valueText = savedFixedValues.trim();
        if (valueText.equals("")) {
            return null;
        }
        return Utils.splitListWithSpaces(valueText);
    }
}
