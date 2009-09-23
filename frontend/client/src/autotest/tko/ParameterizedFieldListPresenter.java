package autotest.tko;

import autotest.common.ui.MultiListSelectPresenter;
import autotest.common.ui.MultiListSelectPresenter.Item;

import com.google.gwt.user.client.ui.HasText;

import java.util.HashMap;
import java.util.Map;

public class ParameterizedFieldListPresenter implements MultiListSelectPresenter.GeneratorHandler {
    public interface Display {
        public HasText addFieldInput(String name);
        public void removeFieldInput(HasText input);
    }

    private int nameCounter;
    private Display display;
    private HeaderFieldCollection headerFields;
    private Map<ParameterizedField, HasText> fieldInputMap = 
        new HashMap<ParameterizedField, HasText>();

    /**
     * @param headerFields Generated ParameterizedFields will be added to this (and removed when
     * they're deleted) 
     */
    public ParameterizedFieldListPresenter(HeaderFieldCollection headerFields) {
        this.headerFields = headerFields;
    }

    public void bindDisplay(Display display) {
        this.display = display;
    }

    @Override
    public Item generateItem(Item generatorItem) {
        String sqlName = generatorItem.value + Integer.toString(nameCounter);
        nameCounter++;
        ParameterizedField field = ParameterizedField.fromSqlName(sqlName);
        addField(field);
        return field.getItem();
    }

    public void addField(ParameterizedField field) {
        headerFields.add(field);

        // ensure name counter never overlaps this field name
        if (nameCounter <= field.getFieldNumber()) {
            nameCounter = field.getFieldNumber() + 1;
        }

        HasText fieldInput = display.addFieldInput(field.getName());
        fieldInputMap.put(field, fieldInput);
    }

    @Override
    public void onRemoveGeneratedItem(Item generatedItem) {
        HeaderField field = headerFields.getFieldByName(generatedItem.name);
        assert field != null;
        HasText fieldInput = fieldInputMap.remove(field);
        display.removeFieldInput(fieldInput);
        headerFields.remove(field);
    }

    public void updateStateFromView() {
        for (ParameterizedField field : fieldInputMap.keySet()) {
            String newValue = fieldInputMap.get(field).getText();
            field.setValue(newValue);
        }
    }

    public void updateViewFromState() {
        for (ParameterizedField field : fieldInputMap.keySet()) {
            fieldInputMap.get(field).setText(field.getValue());
        }
    }

    public boolean areAllInputsFilled() {
        for (HasText fieldInput : fieldInputMap.values()) {
            if (fieldInput.getText().isEmpty()) {
                return false;
            }
        }
        return true;
    }
}
