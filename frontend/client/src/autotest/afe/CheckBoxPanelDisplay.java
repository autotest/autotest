package autotest.afe;

import autotest.afe.ICheckBox.CheckBoxImpl;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;

public class CheckBoxPanelDisplay extends Composite implements CheckBoxPanel.Display {
    private int numColumns;
    private FlexTable table = new FlexTable();

    public CheckBoxPanelDisplay(int numColumns) {
        this.numColumns = numColumns;
        initWidget(table);
    }

    public ICheckBox generateCheckBox(int index) {
        CheckBoxImpl checkbox = new CheckBoxImpl();

        int row = index / numColumns;
        int col = index % numColumns;
        table.setWidget(row, col, checkbox);

        return checkbox;
    }
}
