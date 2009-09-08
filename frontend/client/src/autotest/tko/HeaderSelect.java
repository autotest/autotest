package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.MultiListSelectPresenter;
import autotest.common.ui.ToggleControl;
import autotest.common.ui.MultiListSelectPresenter.Item;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.HasText;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

class HeaderSelect implements ClickHandler, MultiListSelectPresenter.GeneratorHandler {
    public static final String HISTORY_FIXED_VALUES = "_fixed_values";
    
    private final static HeaderField MACHINE_LABELS_FIELD = 
        new SimpleHeaderField("Machine labels...", "");
    
    public interface Display {
        public MultiListSelectPresenter.DoubleListDisplay getDoubleListDisplay();
        public MultiListSelectPresenter.ToggleDisplay getToggleDisplay();

        public HasText getFixedValuesInput();
        public void setFixedValuesVisible(boolean visible);
        public ToggleControl getFixedValuesToggle();

        public MachineLabelDisplay addMachineLabelDisplay(String name);
        public void removeMachineLabelDisplay(MachineLabelDisplay display);
    }

    public interface MachineLabelDisplay {
        public HasText getLabelInput();
    }

    private Map<String, HeaderField> headerMap = new HashMap<String, HeaderField>();
    private Map<MachineLabelField, MachineLabelDisplay> machineLabelInputMap = 
        new HashMap<MachineLabelField, MachineLabelDisplay>();
    
    private List<HeaderField> savedSelectedFields;
    private String savedFixedValues;

    private Display display;
    private MultiListSelectPresenter multiListSelect = new MultiListSelectPresenter();

    public HeaderSelect() {
        multiListSelect.setGeneratorHandler(this);
    }

    public void bindDisplay(Display display) {
        this.display = display;
        display.getFixedValuesToggle().addClickHandler(this);
        display.setFixedValuesVisible(false);
        multiListSelect.bindDisplay(display.getDoubleListDisplay());
        multiListSelect.bindToggleDisplay(display.getToggleDisplay());

        addFieldToMap(MACHINE_LABELS_FIELD);
        multiListSelect.addItem(Item.createGenerator(MACHINE_LABELS_FIELD.getName(), 
                                                     MACHINE_LABELS_FIELD.getSqlName()));
    }

    public void addItem(HeaderField headerField) {
        addFieldToMap(headerField);
        multiListSelect.addItem(Item.createItem(headerField.getName(), headerField.getSqlName()));
    }

    private void addFieldToMap(HeaderField headerField) {
        headerMap.put(headerField.getSqlName(), headerField);
    }

    private void removeFieldFromMap(HeaderField header) {
        HeaderField mappedHeader = headerMap.remove(header.getSqlName());
        assert mappedHeader == header;
    }

    public void updateStateFromView() {
        savedSelectedFields = getSelectedItemsFromView();
        savedFixedValues = getFixedValuesText();
        updateMachineLabelsFromView();
    }
    
    private List<HeaderField> getSelectedItemsFromView() {
        List<HeaderField> selectedFields = new ArrayList<HeaderField>();
        for (Item item : multiListSelect.getSelectedItems()) {
            selectedFields.add(headerMap.get(item.value));
        }
        return selectedFields;
    }
    
    private String getFixedValuesText() {
        if (!isFixedValuesActive()) {
            return "";
        }
        
        return display.getFixedValuesInput().getText();
    }
    
    public List<HeaderField> getSelectedItems() {
        return Collections.unmodifiableList(savedSelectedFields);
    }
    
    public void updateViewFromState() {
        selectItemsInView(savedSelectedFields);
        display.getFixedValuesInput().setText(savedFixedValues);
        display.getFixedValuesToggle().setActive(!savedFixedValues.equals(""));
        updateViewFromMachineLabels();
    }

    private void updateViewFromMachineLabels() {
        for (MachineLabelField field : machineLabelInputMap.keySet()) {
            MachineLabelDisplay display = machineLabelInputMap.get(field);
            String labelString = Utils.joinStrings(",", field.getLabelList());
            display.getLabelInput().setText(labelString);
        }
    }

    private void selectItemsInView(List<HeaderField> fields) {
        List<String> fieldNames = new ArrayList<String>();
        for (HeaderField field : fields) {
            fieldNames.add(field.getName());
        }
        multiListSelect.setSelectedItemsByName(fieldNames);
    }

    public void selectItems(List<HeaderField> fields) {
        savedSelectedFields = new ArrayList<HeaderField>(fields);
        savedFixedValues = "";
    }
    
    public void selectItem(HeaderField field) {
        selectItems(Arrays.asList(new HeaderField[] {field}));
    }

    @Override
    public void onClick(ClickEvent event) {
        assert event.getSource() == display.getFixedValuesToggle();
        display.setFixedValuesVisible(isFixedValuesActive());
    }

    public void addHistoryArguments(Map<String, String> arguments, String name) {
        List<String> fields = new ArrayList<String>();
        for (HeaderField field : getSelectedItems()) {
            fields.add(field.getSqlName());
        }
        String fieldList = Utils.joinStrings(",", fields);
        arguments.put(name, fieldList);
        if (isFixedValuesActive()) {
            arguments.put(name + HISTORY_FIXED_VALUES, display.getFixedValuesInput().getText());
        }
        
        for (MachineLabelField field : machineLabelInputMap.keySet()) {
            String labels = Utils.joinStrings(",", field.getLabelList());
            arguments.put(field.getSqlName(), labels);
        }
    }

    private boolean isFixedValuesActive() {
        return !display.getToggleDisplay().getToggleMultipleLink().isActive()
               && display.getFixedValuesToggle().isActive();
    }

    public void handleHistoryArguments(Map<String, String> arguments, String name) {
        List<HeaderField> headerFields = getHeaderFieldsFromValues(arguments, name);
        selectItems(headerFields);
        String fixedValuesText = arguments.get(name + HISTORY_FIXED_VALUES);
        savedFixedValues = fixedValuesText;
    }

    private List<HeaderField> getHeaderFieldsFromValues(Map<String, String> arguments, 
                                                        String name) {
        String[] fields = arguments.get(name).split(",");
        List<HeaderField> headerFields = new ArrayList<HeaderField>();
        for (String field : fields) {
            if (field.startsWith(MachineLabelField.BASE_SQL_NAME)) {
                MachineLabelField machineLabelField = MachineLabelField.fromFieldSqlName(field);
                List<String> labels = Utils.splitList(arguments.get(field));
                machineLabelField.setLabels(labels);
                Item machineLabelItem = addMachineLabelField(machineLabelField);
                multiListSelect.addItem(machineLabelItem);
            }

            headerFields.add(headerMap.get(field));
        }
        return headerFields;
    }

    private Item addMachineLabelField(MachineLabelField field) {
        addFieldToMap(field);
        MachineLabelDisplay machineLabelDisplay = display.addMachineLabelDisplay(field.getName());
        machineLabelInputMap.put(field, machineLabelDisplay);
        return Item.createGeneratedItem(field.getName(), field.getSqlName());
    }

    @Override
    public Item generateItem(Item generatorItem) {
        assert generatorItem.name.equals(MACHINE_LABELS_FIELD.getName());
        return addMachineLabelField(MachineLabelField.newInstance());
    }

    @Override
    public void onRemoveGeneratedItem(Item generatedItem) {
        HeaderField field = headerMap.get(generatedItem.value);
        assert field instanceof MachineLabelField;
        removeFieldFromMap(field);
        MachineLabelDisplay machineLabelDisplay = machineLabelInputMap.remove(field);
        display.removeMachineLabelDisplay(machineLabelDisplay);
    }

    private void updateMachineLabelsFromView() {
        for (MachineLabelField field : machineLabelInputMap.keySet()) {
            MachineLabelDisplay display = machineLabelInputMap.get(field);
            String labelString = display.getLabelInput().getText();
            field.setLabels(Utils.splitListWithSpaces(labelString));
        }
    }
    
    /**
     * @return true if all machine label header inputs are not empty.
     */
    public boolean checkMachineLabelHeaders() {
        for (MachineLabelDisplay display : machineLabelInputMap.values()) {
            if (display.getLabelInput().getText().isEmpty()) {
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
