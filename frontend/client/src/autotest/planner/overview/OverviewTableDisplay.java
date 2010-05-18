package autotest.planner.overview;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;

import java.util.List;

public class OverviewTableDisplay extends Composite implements OverviewTable.Display {

    private FlexTable table = new FlexTable();

    public OverviewTableDisplay() {
        table.setStyleName("overview_table");

        table.setText(0, 0, "");
        table.setText(0, 1, "");

        table.getRowFormatter().addStyleName(0, "header");
        table.getColumnFormatter().addStyleName(0, "header");
        table.getColumnFormatter().addStyleName(1, "header");

        initWidget(table);

        setVisible(false);
    }

    @Override
    public void addData(String header, List<String> data) {
        assert table.getRowCount() == data.size() + 1;

        setVisible(true);

        setData(0, header);
        for (int i = 0; i < data.size(); i++) {
            setData(i + 1, data.get(i));
        }
    }

    private void setData(int row, String data) {
        int cell = table.getCellCount(row);
        table.setText(row, cell, data);
        if (!table.getCellFormatter().getStyleName(row, cell).equals("header") &&
                row > 0 && row % 2 == 0) {
            table.getCellFormatter().addStyleName(row, cell, "even");
        }
    }

    @Override
    public void addHeaderGroup(String group, String[] headers) {
        int row = table.getRowCount();

        table.setText(row, 0, group);
        table.getFlexCellFormatter().setRowSpan(row, 0, headers.length);

        for (int i = 0; i < headers.length; i++) {
            int cell = 0;
            if (i == 0) {
                cell = 1;
            }
            table.setText(row + i, cell, headers[i]);
        }
    }

    @Override
    public void clearAllData() {
        for (int row = 0; row < table.getRowCount(); row++) {
            for (int col = 2; col < table.getCellCount(row); col++) {
                table.removeCell(row, col);
            }
        }
        setVisible(false);
    }

}
