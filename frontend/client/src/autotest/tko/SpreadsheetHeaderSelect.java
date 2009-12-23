package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.MultiListSelectPresenter;
import autotest.common.ui.ToggleControl;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.HasText;

import java.util.Arrays;
import java.util.List;
import java.util.Map;

public class SpreadsheetHeaderSelect implements ClickHandler {
    public static final String HISTORY_FIXED_VALUES = "_fixed_values";

    public static class State {
        private HeaderSelect.State baseState = new HeaderSelect.State();
        private String fixedValues;
    }

    public interface Display {
        public MultiListSelectPresenter.DoubleListDisplay getDoubleListDisplay();
        public MultiListSelectPresenter.ToggleDisplay getToggleDisplay();
        public HasText getFixedValuesInput();
        public void setFixedValuesVisible(boolean visible);
        public ToggleControl getFixedValuesToggle();
    }

    private Display display;
    private final State savedState = new State();
    private HeaderSelect headerSelect;

    public SpreadsheetHeaderSelect(HeaderFieldCollection headerFields) {
        headerSelect = new HeaderSelect(headerFields, savedState.baseState);
    }

    public void bindDisplay(Display display) {
        this.display = display;

        headerSelect.bindDisplay(display.getDoubleListDisplay());
        headerSelect.multiListSelect.bindToggleDisplay(display.getToggleDisplay());
        display.getFixedValuesToggle().addClickHandler(this);
        display.setFixedValuesVisible(false);
    }

    protected void saveToState(State state) {
        headerSelect.saveToState(state.baseState);
        state.fixedValues = getFixedValuesText();
    }

    private String getFixedValuesText() {
        if (!isFixedValuesActive()) {
            return "";
        }
        
        return display.getFixedValuesInput().getText();
    }

    private List<String> getFixedValues() {
        String valueText = savedState.fixedValues.trim();
        if (valueText.equals("")) {
            return null;
        }
        return Utils.splitListWithSpaces(valueText);
    }

    private boolean isFixedValuesActive() {
        return !display.getToggleDisplay().getToggleMultipleLink().isActive()
               && display.getFixedValuesToggle().isActive();
    }

    public void loadFromState(State state) {
        headerSelect.loadFromState(state.baseState);
        display.getFixedValuesInput().setText(state.fixedValues);
        display.getFixedValuesToggle().setActive(!state.fixedValues.equals(""));
    }

    public void setSelectedItems(List<HeaderField> fields) {
        headerSelect.setSelectedItems(fields);
        savedState.fixedValues = "";
    }

    public void onClick(ClickEvent event) {
        assert event.getSource() == display.getFixedValuesToggle();
        display.setFixedValuesVisible(isFixedValuesActive());
    }

    public void addHistoryArguments(Map<String, String> arguments, String name) {
        headerSelect.addHistoryArguments(arguments, name);
        if (isFixedValuesActive()) {
            arguments.put(name + HISTORY_FIXED_VALUES, display.getFixedValuesInput().getText());
        }
    }

    public void handleHistoryArguments(Map<String, String> arguments, String name) {
        headerSelect.handleHistoryArguments(arguments, name);
        String fixedValuesText = arguments.get(name + HISTORY_FIXED_VALUES);
        savedState.fixedValues = fixedValuesText;
    }

    public void addQueryParameters(JSONObject parameters) {
        List<String> fixedValues = getFixedValues();
        if (fixedValues != null) {
            JSONObject fixedValuesObject = 
                Utils.setDefaultValue(parameters, "fixed_headers", new JSONObject()).isObject();
            fixedValuesObject.put(getSelectedItems().get(0).getSqlName(), 
                                  Utils.stringsToJSON(fixedValues));
        }
    }

    public List<HeaderField> getSelectedItems() {
        return headerSelect.getSelectedItems();
    }

    public void refreshFields() {
        headerSelect.refreshFields();
    }

    public void setSelectedItem(HeaderField field) {
        setSelectedItems(Arrays.asList(new HeaderField[] {field}));
    }

    public State getStateFromView() {
        State state = new State();
        saveToState(state);
        return state;
    }

    public void updateStateFromView() {
        saveToState(savedState);
    }

    public void updateViewFromState() {
        loadFromState(savedState);
    }
}
