package autotest.tko;

import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.SimplifiedList;
import autotest.tko.ParameterizedFieldListPresenter.Display;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;

public class ParameterizedFieldListDisplay extends Composite implements Display {
    private static class FieldWidget implements Display.FieldWidget {
        private String label;
        private Anchor deleteLink = new Anchor("[X]");

        public FieldWidget(String label) {
            this.label = label;
        }

        public String getLabel() {
            return label;
        }

        @Override
        public HasClickHandlers getDeleteLink() {
            return deleteLink;
        }
    }

    private ExtendedListBox typeSelect = new ExtendedListBox();
    private TextBox valueInput = new TextBox();
    private Anchor addLink = new Anchor("Add");
    private FlexTable fieldTable = new FlexTable();

    public ParameterizedFieldListDisplay() {
        Panel addFieldPanel = new HorizontalPanel();
        addFieldPanel.add(new Label("Add custom field:"));
        addFieldPanel.add(typeSelect);
        addFieldPanel.add(valueInput);
        addFieldPanel.add(addLink);

        fieldTable.setText(0, 0, "Field name");
        fieldTable.setText(0, 1, "Filtering name");
        fieldTable.setCellSpacing(0);
        fieldTable.setStylePrimaryName("data-table");
        fieldTable.getRowFormatter().setStyleName(0, "data-row-header");
        setFieldTableVisible();

        Panel container = new VerticalPanel();
        container.add(fieldTable);
        container.add(addFieldPanel);
        initWidget(container);
    }

    private void setFieldTableVisible() {
        boolean visible = (fieldTable.getRowCount() > 1);
        fieldTable.setVisible(visible);
    }

    @Override
    public HasClickHandlers getAddLink() {
        return addLink;
    }

    @Override
    public SimplifiedList getTypeSelect() {
        return typeSelect;
    }

    @Override
    public HasText getValueInput() {
        return valueInput;
    }

    @Override
    public Display.FieldWidget addFieldWidget(String name, String filteringName) {
        int row = fieldTable.getRowCount();
        FieldWidget widget = new FieldWidget(name);
        fieldTable.setText(row, 0, name);
        fieldTable.setText(row, 1, filteringName);
        fieldTable.setWidget(row, 2, widget.deleteLink);
        setFieldTableVisible();
        return widget;
    }

    @Override
    public void removeFieldWidget(Display.FieldWidget widget) {
        FieldWidget fieldWidget = (FieldWidget) widget;
        for (int row = 1; row < fieldTable.getRowCount(); row++) {
            if (fieldTable.getText(row, 0).equals(fieldWidget.getLabel())) {
                fieldTable.removeRow(row);
                setFieldTableVisible();
                return;
            }
        }

        throw new IllegalArgumentException("Unable to find field widget " + widget);
    }
}
