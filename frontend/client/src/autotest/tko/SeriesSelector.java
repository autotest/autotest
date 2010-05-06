package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.ExtendedListBox;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HasHorizontalAlignment;
import com.google.gwt.user.client.ui.HasVerticalAlignment;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class SeriesSelector extends Composite {

    private FlexTable table = new FlexTable();
    private ArrayList<Series> series = new ArrayList<Series>();
    private Anchor addLink = new Anchor("[Add Series]");
    private boolean enabled = true;
    private boolean invertible = false;
    private final ChangeHandler handler;

    public class Series extends Composite {

        private FlexTable seriesTable = new FlexTable();
        private TextBox name = new TextBox();
        private CheckBox invert = new CheckBox("Invert y-axis");
        private ExtendedListBox values = new DBColumnSelector(DBColumnSelector.PERF_VIEW);
        private ExtendedListBox aggregation = new ExtendedListBox();
        private CheckBox errorBars = new CheckBox();
        private FilterSelector filter = new FilterSelector(DBColumnSelector.PERF_VIEW);
        private Anchor deleteLink = new Anchor("Delete Series");
        private int row;

        private Series(int aRow) {
            this.row = aRow;
            deleteLink.addClickHandler(new ClickHandler() {
                public void onClick(ClickEvent event) {
                    if (enabled) {
                        deleteSeries(row);
                    }
                }
            });

            name.addChangeHandler(handler);

            aggregation.addItem("AVG", "AVG(");
            aggregation.addItem("COUNT (DISTINCT)", "COUNT(DISTINCT ");
            aggregation.addItem("MIN", "MIN(");
            aggregation.addItem("MAX", "MAX(");
            aggregation.setSelectedIndex(0);
            aggregation.addChangeHandler(new ChangeHandler() {
                public void onChange(ChangeEvent event) {
                    if (getAggregation().equals("AVG(")) {
                        errorBars.setEnabled(true);
                    } else {
                        errorBars.setEnabled(false);
                        errorBars.setValue(false);
                    }
                }
            });

            errorBars.setText("error bars");

            Panel aggregationPanel = new HorizontalPanel();
            aggregationPanel.add(aggregation);
            aggregationPanel.add(errorBars);

            addControl("Name:", name);
            addControl("Values:", values);
            addControl("Aggregation:", aggregationPanel);
            addControl("Filters:", filter);
            seriesTable.getFlexCellFormatter().setVerticalAlignment(
                    seriesTable.getRowCount() - 1, 0, HasVerticalAlignment.ALIGN_TOP);

            seriesTable.setWidget(seriesTable.getRowCount() - 1, 2, deleteLink);
            seriesTable.getFlexCellFormatter().setHorizontalAlignment(
                    seriesTable.getRowCount() - 1, 2, HasHorizontalAlignment.ALIGN_RIGHT);
            seriesTable.getFlexCellFormatter().setVerticalAlignment(
                    seriesTable.getRowCount() - 1, 2, HasVerticalAlignment.ALIGN_BOTTOM);

            seriesTable.setWidget(0, 2, invert);
            seriesTable.getFlexCellFormatter().setHorizontalAlignment(
                    0, 2, HasHorizontalAlignment.ALIGN_RIGHT);

            initWidget(seriesTable);
        }

        private void addControl(String text, Widget control) {
            TkoUtils.addControlRow(seriesTable, text, control);
        }

        public String getAggregation() {
            return aggregation.getSelectedValue();
        }

        public ExtendedListBox getDBColumnSelector() {
            return values;
        }

        public boolean wantErrorBars() {
            return errorBars.getValue();
        }

        public String getName() {
            return name.getText();
        }

        public String getFilterString() {
            return filter.getFilterString();
        }

        public void setInverted(boolean isInverted) {
            invert.setValue(isInverted);
        }

        public void addToHistory(Map<String, String> args, int index) {
            args.put(parameterString("name", index), getName());
            args.put(parameterString("values", index), getDBColumnSelector().getSelectedValue());
            args.put(parameterString("aggregation", index), aggregation.getSelectedName());
            args.put(parameterString("errorBars", index), String.valueOf(wantErrorBars()));
            filter.addToHistory(args, parameterString("seriesFilters", index));
        }

        public void readHistoryArguments(Map<String, String> args, int index) {
            name.setText(args.get(parameterString("name", index)));

            String valueColumn = args.get(parameterString("values", index));
            getDBColumnSelector().selectByValue(valueColumn);

            String aggregationString = args.get(parameterString("aggregation", index));
            aggregation.selectByName(aggregationString);

            boolean errorBarsChecked =
                Boolean.parseBoolean(args.get(parameterString("errorBars", index)));
            errorBars.setValue(errorBarsChecked);

            filter.handleHistoryArguments(args, parameterString("seriesFilters", index));
        }
    }

    public SeriesSelector(ChangeHandler handler) {
        this.handler = handler;

        addLink.addClickHandler(new ClickHandler() {
            public void onClick(ClickEvent event) {
                if (enabled) {
                    addSeries();
                }
            }
        });
        table.setWidget(0, 0, addLink);
        table.setText(0, 1, "");

        addSeries();

        initWidget(table);
    }

    public List<Series> getAllSeries() {
        return Collections.unmodifiableList(series);
    }

    public void reset() {
        for (int i = 0; i < series.size(); i++) {
            table.removeRow(0);
        }
        series.clear();
        addSeries();
    }

    public List<String> getInverted() {
        List<String> inverted = new ArrayList<String>();
        for (Series s : series) {
            if (s.invert.getValue()) {
                inverted.add(s.getName());
            }
        }
        return inverted;
    }

    public void setInvertible(boolean invertible) {
        for (Series s : series) {
            s.invert.setEnabled(invertible);
            if (!invertible) {
                s.invert.setValue(false);
            }
        }
        this.invertible = invertible;
    }

    private static String parameterString(String parameterName, int index) {
        return parameterName + "[" + index + "]";
    }

    protected void addToHistory(Map<String, String> args) {
        for (int index = 0; index < series.size(); index++) {
            series.get(index).addToHistory(args, index);
        }
        List<String> inverted = getInverted();
        if (!inverted.isEmpty()) {
            args.put("inverted", Utils.joinStrings(",", inverted));
        }
    }

    protected void handleHistoryArguments(Map<String, String> args) {
        String invertedString = args.get("inverted");
        Set<String> inverted = new HashSet<String>();
        if (invertedString != null) {
            for (String s : invertedString.split(",")) {
                inverted.add(s);
            }
        }

        for (int index = 0; args.get(parameterString("name", index)) != null; index++) {
            Series thisSeries;
            if (index == 0) {
                thisSeries = series.get(0);
            } else {
                thisSeries = addSeries();
            }

            thisSeries.readHistoryArguments(args, index);
            thisSeries.setInverted(inverted.contains(thisSeries.getName()));
        }
    }

    private Series addSeries() {
        int row = table.getRowCount() - 1;
        Series nextSeries = new Series(row);
        nextSeries.invert.setEnabled(invertible);
        series.add(nextSeries);
        table.insertRow(row);
        table.setWidget(row, 0, nextSeries);
        table.getFlexCellFormatter().setColSpan(row, 0, 2);
        table.getFlexCellFormatter().setStylePrimaryName(row, 0, "box");
        return nextSeries;
    }

    private void deleteSeries(int row) {
        if (series.size() == 1) {
            reset();
            return;
        }

        series.remove(row);
        table.removeRow(row);
        for (int i = row; i < series.size(); i++) {
            series.get(i).row--;
        }
    }
}
