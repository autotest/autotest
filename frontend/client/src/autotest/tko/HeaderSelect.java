package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.MultiListSelectPresenter;
import autotest.common.ui.MultiListSelectPresenter.DoubleListDisplay;
import autotest.common.ui.MultiListSelectPresenter.GeneratorHandler;
import autotest.common.ui.MultiListSelectPresenter.Item;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

class HeaderSelect {
    public static class State {
        private List<HeaderField> selectedFields;

        public List<HeaderField> getSelectedFields() {
            return new ArrayList<HeaderField>(selectedFields);
        }
    }
    
    private HeaderFieldCollection headerFields;
    private final State savedState;

    protected MultiListSelectPresenter multiListSelect = new MultiListSelectPresenter();

    public HeaderSelect(HeaderFieldCollection headerFields, State state) {
        this.headerFields = headerFields;
        savedState = state;
    }

    public void bindDisplay(DoubleListDisplay display) {
        multiListSelect.bindDisplay(display);
        refreshFields();
    }

    public void refreshFields() {
        List<Item> selection = multiListSelect.getSelectedItems();
        multiListSelect.clearItems();
        for (HeaderField field : headerFields) {
            if (field.isUserSelectable()) {
                multiListSelect.addItem(field.getItem());
            }
        }
        multiListSelect.restoreSelectedItems(selection);
    }

    public void updateStateFromView() {
        saveToState(savedState);
    }

    protected void saveToState(State state) {
        state.selectedFields = getSelectedItemsFromView();
    }
    
    public State getStateFromView() {
        State state = new State();
        saveToState(state);
        return state;
    }
    
    private List<HeaderField> getSelectedItemsFromView() {
        List<HeaderField> selectedFields = new ArrayList<HeaderField>();
        for (Item item : multiListSelect.getSelectedItems()) {
            selectedFields.add(headerFields.getFieldBySqlName(item.value));
        }
        return selectedFields;
    }
    
    public List<HeaderField> getSelectedItems() {
        return savedState.getSelectedFields();
    }
    
    public void updateViewFromState() {
        loadFromState(savedState);
    }

    public void loadFromState(State state) {
        setSelectedItemsInView(state.selectedFields);
    }

    private void setSelectedItemsInView(List<HeaderField> fields) {
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

    public void setSelectedItems(List<HeaderField> fields) {
        savedState.selectedFields = new ArrayList<HeaderField>(fields);
    }
    
    public void setSelectedItem(HeaderField field) {
        setSelectedItems(Arrays.asList(new HeaderField[] {field}));
    }
    
    public void selectItemInView(HeaderField field) {
        List<HeaderField> fields = getSelectedItemsFromView();
        if (!fields.contains(field)) {
            fields.add(field);
            setSelectedItemsInView(fields);
        }
    }
    
    public void deselectItemInView(HeaderField field) {
        List<HeaderField> fields = getSelectedItemsFromView();
        if (fields.remove(field)) {
            setSelectedItemsInView(fields);
        }
    }

    public void addHistoryArguments(Map<String, String> arguments, String name) {
        List<String> fields = new ArrayList<String>();
        for (HeaderField field : getSelectedItems()) {
            fields.add(field.getSqlName());
        }
        String fieldList = Utils.joinStrings(",", fields);
        arguments.put(name, fieldList);
    }

    public void handleHistoryArguments(Map<String, String> arguments, String name) {
        String[] fields = arguments.get(name).split(",");
        List<HeaderField> selectedFields = getHeaderFieldsFromValues(fields);
        setSelectedItems(selectedFields);
    }

    private List<HeaderField> getHeaderFieldsFromValues(String[] fieldSqlNames) {
        List<HeaderField> fields = new ArrayList<HeaderField>();
        for (String sqlName : fieldSqlNames) {
            fields.add(headerFields.getFieldBySqlName(sqlName));
        }
        return fields;
    }

    protected State getState() {
        return savedState;
    }

    public void setGeneratorHandler(GeneratorHandler handler) {
        multiListSelect.setGeneratorHandler(handler);
    }
}
