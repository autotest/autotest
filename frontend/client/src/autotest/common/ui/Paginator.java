package autotest.common.ui;

import autotest.common.SimpleCallback;

import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.FlowPanel;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Hyperlink;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.List;

/**
 * A widget to faciliate pagination of tables.  Shows currently displayed rows, 
 * total row count, and buttons for moving among pages.
 */
public class Paginator extends Composite {
    static class LinkWithDisable extends Composite {
        protected Panel panel = new FlowPanel();
        protected Label label;
        protected Hyperlink link;
        
        public LinkWithDisable(String text) {
            label = new Label(text);
            link = new SimpleHyperlink(text);
            panel.add(link);
            panel.add(label);
            link.setStyleName("paginator-link");
            label.setStyleName("paginator-link");
            setEnabled(false); // default to not enabled
            initWidget(panel);
        }
        
        public void setEnabled(boolean enabled) {
            link.setVisible(enabled);
            label.setVisible(!enabled);
        }

        public void addClickListener(ClickListener listener) {
            link.addClickListener(listener);
        }

        public void removeClickListener(ClickListener listener) {
            link.removeClickListener(listener);
        }
    }

    protected int resultsPerPage, numTotalResults;
    protected List<SimpleCallback> changeListeners =
        new ArrayList<SimpleCallback>();
    protected int currentStart = 0;

    protected HorizontalPanel mainPanel = new HorizontalPanel();
    protected LinkWithDisable nextControl, prevControl, 
                              firstControl, lastControl;
    protected Label statusLabel = new Label();

    public Paginator() {
        prevControl = new LinkWithDisable("< Previous");
        prevControl.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                currentStart -= Paginator.this.resultsPerPage;
                notifyListeners();
            }
        });
        nextControl = new LinkWithDisable("Next >");
        nextControl.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                currentStart += Paginator.this.resultsPerPage;
                notifyListeners();
            }
        });
        firstControl = new LinkWithDisable("<< First");
        firstControl.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                currentStart = 0;
                notifyListeners();
            } 
        });
        lastControl = new LinkWithDisable("Last >>");
        lastControl.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                currentStart = getLastPageStart();
                notifyListeners();
            } 
        });
        
        statusLabel.setWidth("10em");
        statusLabel.setHorizontalAlignment(Label.ALIGN_CENTER);
        
        mainPanel.setVerticalAlignment(HorizontalPanel.ALIGN_MIDDLE);
        mainPanel.add(firstControl);
        mainPanel.add(prevControl);
        mainPanel.add(statusLabel);
        mainPanel.add(nextControl);
        mainPanel.add(lastControl);
        
        initWidget(mainPanel);
    }
    
    /**
     * Get the current starting row index.
     */
    public int getStart() {
        return currentStart;
    }
    
    /**
     * Get the current ending row index (one past the last currently displayed 
     * row).
     */
    public int getEnd() {
        int end = currentStart + resultsPerPage;
        if (end < numTotalResults)
            return end;
        return numTotalResults;
    }
    
    /**
     * Get the size of each page.
     */
    public int getResultsPerPage() {
        return resultsPerPage;
    }
    
    /**
     * Set the size of a page.
     */
    public void setResultsPerPage(int resultsPerPage) {
        this.resultsPerPage = resultsPerPage;
    }

    /**
     * Set the total number of results in the current working set.
     */
    public void setNumTotalResults(int numResults) {
        this.numTotalResults = numResults;
        if (currentStart >= numResults)
            currentStart = getLastPageStart();
    }
    
    /**
     * Set the current starting index.
     */
    public void setStart(int start) {
        this.currentStart = start;
    }
    
    protected int getLastPageStart() {
        // compute start of last page using truncation
        return ((numTotalResults - 1) / resultsPerPage) * resultsPerPage;
    }

    public void update() {
        boolean prevEnabled = !(currentStart == 0);
        boolean nextEnabled = currentStart + resultsPerPage < numTotalResults;
        firstControl.setEnabled(prevEnabled);
        prevControl.setEnabled(prevEnabled);
        nextControl.setEnabled(nextEnabled);
        lastControl.setEnabled(nextEnabled);
        int displayStart = getStart() + 1;
        if(numTotalResults == 0)
            displayStart = 0;
        statusLabel.setText(displayStart + "-" + getEnd() + 
                            " of " + numTotalResults); 
    }
    
    public void addChangeListener(SimpleCallback listener) {
        changeListeners.add(listener);
    }
    
    public void removeChangeListener(SimpleCallback listener) {
        changeListeners.remove(listener);
    }
    
    protected void notifyListeners() {
        for (SimpleCallback listener : changeListeners) {
            listener.doCallback(this);
        }
    }
}
