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
import java.util.List;
import java.util.Map;

class HeaderSelect implements ClickHandler {
    public static final String HISTORY_FIXED_VALUES = "_fixed_values";

    public interface Display {
        public MultiListSelectPresenter.DoubleListDisplay getDoubleListDisplay();
        public MultiListSelectPresenter.ToggleDisplay getToggleDisplay();
        public ParameterizedFieldListPresenter.Display getParameterizedFieldDisplay();

        public HasText getFixedValuesInput();
        public void setFixedValuesVisible(boolean visible);
        public ToggleControl getFixedValuesToggle();
    }

    private HeaderFieldCollection headerFields;
    
    private List<HeaderField> savedSelectedFields;
    private String savedFixedValues;

    private Display display;
    private MultiListSelectPresenter multiListSelect = new MultiListSelectPresenter();
    private ParameterizedFieldListPresenter parameterizedFieldPresenter; 

    public HeaderSelect(HeaderFieldCollection headerFields) {
        this.headerFields = headerFields;
        parameterizedFieldPresenter = new ParameterizedFieldListPresenter(headerFields);
        multiListSelect.setGeneratorHandler(parameterizedFieldPresenter);
    }

    public void bindDisplay(Display display) {
        this.display = display;
        display.getFixedValuesToggle().addClickHandler(this);
        display.setFixedValuesVisible(false);
        multiListSelect.bindDisplay(display.getDoubleListDisplay());
        multiListSelect.bindToggleDisplay(display.getToggleDisplay());
        parameterizedFieldPresenter.bindDisplay(display.getParameterizedFieldDisplay());

        for (HeaderField field : headerFields) {
            multiListSelect.addItem(field.getItem());
        }
        multiListSelect.addItem(ParameterizedField.getGenerator(MachineLabelField.BASE_NAME));
    }

    public void updateStateFromView() {
        savedSelectedFields = getSelectedItemsFromView();
        savedFixedValues = getFixedValuesText();
        parameterizedFieldPresenter.updateStateFromView();
    }
    
    private List<HeaderField> getSelectedItemsFromView() {
        List<HeaderField> selectedFields = new ArrayList<HeaderField>();
        for (Item item : multiListSelect.getSelectedItems()) {
            selectedFields.add(headerFields.getFieldBySqlName(item.value));
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
        parameterizedFieldPresenter.updateViewFromState();
    }

    private void selectItemsInView(List<HeaderField> fields) {
        List<String> fieldNames = new ArrayList<String>();
        for (HeaderField field : fields) {
            Item item = field.getItem();
            if (item.isGeneratedItem) {
                multiListSelect.addItem(item);
            }
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

        headerFields.addHistoryArguments(arguments);
    }

    private boolean isFixedValuesActive() {
        return !display.getToggleDisplay().getToggleMultipleLink().isActive()
               && display.getFixedValuesToggle().isActive();
    }

    public void handleHistoryArguments(Map<String, String> arguments, String name) {
        String[] fields = arguments.get(name).split(",");
        addParameterizedFields(fields);
        headerFields.handleHistoryArguments(arguments);
        List<HeaderField> selectedFields = getHeaderFieldsFromValues(fields);
        selectItems(selectedFields);
        String fixedValuesText = arguments.get(name + HISTORY_FIXED_VALUES);
        savedFixedValues = fixedValuesText;
    }

    private void addParameterizedFields(String[] sqlNames) {
        for (String sqlName : sqlNames) {
            if (!headerFields.containsSqlName(sqlName)) {
                ParameterizedField field = ParameterizedField.fromSqlName(sqlName);
                parameterizedFieldPresenter.addField(field);
            }
        }
    }

    private List<HeaderField> getHeaderFieldsFromValues(String[] fieldSqlNames) {
        List<HeaderField> fields = new ArrayList<HeaderField>();
        for (String sqlName : fieldSqlNames) {
            fields.add(headerFields.getFieldBySqlName(sqlName));
        }
        return fields;
    }

    /**
     * @return true if all machine label header inputs are not empty.
     */
    public boolean checkMachineLabelHeaders() {
        return parameterizedFieldPresenter.areAllInputsFilled();
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
