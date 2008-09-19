package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.SimpleHyperlink;

import com.google.gwt.user.client.ui.ChangeListener;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.HasHorizontalAlignment;
import com.google.gwt.user.client.ui.HasVerticalAlignment;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class SeriesSelector extends Composite {
    
    private FlexTable table = new FlexTable();
    private ArrayList<Series> series = new ArrayList<Series>();
    private SimpleHyperlink addLink = new SimpleHyperlink("[Add Series]");
    private boolean enabled = true;
    private boolean invertible = false;
    private final ChangeListener listener;
    
    public class Series extends Composite {
        
        private FlexTable seriesTable = new FlexTable();
        private TextBox name = new TextBox();
        private CheckBox invert = new CheckBox("Invert y-axis");
        private DBColumnSelector values = new DBColumnSelector(DBColumnSelector.PERF_VIEW);
        private ListBox aggregation = new ListBox();
        private CheckBox errorBars = new CheckBox();
        private FilterSelector filter = new FilterSelector(DBColumnSelector.PERF_VIEW);
        private SimpleHyperlink deleteLink = new SimpleHyperlink("Delete Series");
        private int row;
        
        private Series(int aRow) {
            this.row = aRow;
            deleteLink.addClickListener(new ClickListener() {
                public void onClick(Widget w) {
                    if (enabled) {
                        deleteSeries(row);
                    }
                }
            });
            
            name.addChangeListener(listener);
            
            aggregation.addItem("AVG", "AVG(");
            aggregation.addItem("COUNT (DISTINCT)", "COUNT(DISTINCT ");
            aggregation.addItem("MIN", "MIN(");
            aggregation.addItem("MAX", "MAX(");
            aggregation.addChangeListener(new ChangeListener() {
                public void onChange(Widget w) {
                    int index = aggregation.getSelectedIndex();
                    if (index == -1) {
                        return;
                    }
                    
                    if (aggregation.getValue(index).equals("AVG(")) {
                        errorBars.setEnabled(true);
                    } else {
                        errorBars.setEnabled(false);
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
            int nextRow = seriesTable.getRowCount();
            seriesTable.setText(nextRow, 0, text);
            seriesTable.getFlexCellFormatter().setStylePrimaryName(nextRow, 0, "field-name");
            seriesTable.setWidget(nextRow, 1, control);
        }
        
        public String getAggregation() {
            return aggregation.getValue(aggregation.getSelectedIndex());
        }
        
        public DBColumnSelector getDBColumnSelector() {
            return values;
        }
        
        public boolean wantErrorBars() {
            int index = aggregation.getSelectedIndex();
            return (index != -1 &&
                    aggregation.getValue(index).equals("AVG(") &&
                    errorBars.isChecked());
        }
        
        public String getName() {
            return name.getText();
        }
        
        public String getFilterString() {
            return filter.getFilterString();
        }
    }
    
    public SeriesSelector(ChangeListener listener) {
        this.listener = listener;
        
        addLink.addClickListener(new ClickListener() {
            public void onClick(Widget w) {
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
    
    public ArrayList<Series> getAllSeries() {
        return series;
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
            if (s.invert.isChecked()) {
                inverted.add(s.getName());
            }
        }
        return inverted;
    }
    
    public void setInvertible(boolean invertible) {
        for (Series s : series) {
            s.invert.setEnabled(invertible);
            if (!invertible) {
                s.invert.setChecked(false);
            }
        }
        this.invertible = invertible;
    }
    
    protected void addToHistory(Map<String, String> args) {
        for (int index = 0; index < series.size(); index++) {
            Series s = series.get(index);
            args.put("name[" + index + "]", s.getName());
            args.put("values[" + index + "]", s.getDBColumnSelector().getColumn());
            args.put("aggregation[" + index + "]",
                    s.aggregation.getItemText(s.aggregation.getSelectedIndex()));
            args.put("errorBars[" + index + "]", String.valueOf(s.wantErrorBars()));
            s.filter.addToHistory(args, "seriesFilters[" + index + "]");
        }
        List<String> inverted = getInverted();
        if (!inverted.isEmpty()) {
            args.put("inverted", Utils.joinStrings(",", inverted));
            System.out.println(args.get("inverted"));
        }
    }
    
    protected void handleHistoryArguments(Map<String, String> args) {
        int index = 0;
        
        String invertedString = args.get("inverted");
        Set<String> inverted = null;
        if (invertedString != null) {
            inverted = new HashSet<String>();
            for (String s : invertedString.split(",")) {
                inverted.add(s);
            }
        }
        
        String name;
        while ((name = args.get("name[" + index + "]")) != null) {
            Series s;
            if (index == 0) {
                s = (Series) table.getWidget(0, 0);
            } else {
                s = addSeries();
            }
            s.name.setText(name);
            s.getDBColumnSelector().selectColumn(args.get("values[" + index + "]"));
            String aggregation = args.get("aggregation[" + index + "]");
            for (int i = 0; i < s.aggregation.getItemCount(); i++) {
                if (s.aggregation.getItemText(i).equals(aggregation)) {
                    s.aggregation.setSelectedIndex(i);
                    break;
                }
            }
            s.errorBars.setChecked(Boolean.parseBoolean(args.get("errorBars[" + index + "]")));
            s.filter.handleHistoryArguments(args, "seriesFilters[" + index + "]");
            s.invert.setChecked(inverted != null && inverted.contains(name));
            
            index++;
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
